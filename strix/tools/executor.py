import inspect
import os
from typing import Any

import httpx


if os.getenv("STRIX_SANDBOX_MODE", "false").lower() == "false":
    from strix.runtime import get_runtime

from .argument_parser import convert_arguments
from .registry import (
    get_tool_by_name,
    get_tool_names,
    needs_agent_state,
    should_execute_in_sandbox,
)


# Reduced from 500s to 90s default - tools shouldn't hang for 8+ minutes
# This timeout must be greater than STRIX_TOOL_EXECUTION_TIMEOUT in tool_server.py
SANDBOX_EXECUTION_TIMEOUT = float(os.getenv("STRIX_SANDBOX_EXECUTION_TIMEOUT", "90"))
SANDBOX_CONNECT_TIMEOUT = float(os.getenv("STRIX_SANDBOX_CONNECT_TIMEOUT", "10"))


async def execute_tool(tool_name: str, agent_state: Any | None = None, **kwargs: Any) -> Any:
    execute_in_sandbox = should_execute_in_sandbox(tool_name)
    sandbox_mode = os.getenv("STRIX_SANDBOX_MODE", "false").lower() == "true"

    if execute_in_sandbox and not sandbox_mode:
        return await _execute_tool_in_sandbox(tool_name, agent_state, **kwargs)

    return await _execute_tool_locally(tool_name, agent_state, **kwargs)


async def _execute_tool_in_sandbox(tool_name: str, agent_state: Any, **kwargs: Any) -> Any:
    if not hasattr(agent_state, "sandbox_id") or not agent_state.sandbox_id:
        raise ValueError("Agent state with a valid sandbox_id is required for sandbox execution.")

    if not hasattr(agent_state, "sandbox_token") or not agent_state.sandbox_token:
        raise ValueError(
            "Agent state with a valid sandbox_token is required for sandbox execution."
        )

    if (
        not hasattr(agent_state, "sandbox_info")
        or "tool_server_port" not in agent_state.sandbox_info
    ):
        raise ValueError(
            "Agent state with a valid sandbox_info containing tool_server_port is required."
        )

    runtime = get_runtime()
    tool_server_port = agent_state.sandbox_info["tool_server_port"]
    server_url = await runtime.get_sandbox_url(agent_state.sandbox_id, tool_server_port)
    request_url = f"{server_url}/execute"

    agent_id = getattr(agent_state, "agent_id", "unknown")

    request_data = {
        "agent_id": agent_id,
        "tool_name": tool_name,
        "kwargs": kwargs,
    }

    headers = {
        "Authorization": f"Bearer {agent_state.sandbox_token}",
        "Content-Type": "application/json",
    }

    timeout = httpx.Timeout(
        timeout=SANDBOX_EXECUTION_TIMEOUT,
        connect=SANDBOX_CONNECT_TIMEOUT,
    )

    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            response = await client.post(
                request_url, json=request_data, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("error"):
                error_msg = response_data['error']
                # Check if it's a network-related error inside the sandbox
                network_errors = ["network", "connection", "dns", "timeout", "unreachable", "refused"]
                if any(err in error_msg.lower() for err in network_errors):
                    raise RuntimeError(
                        f"Sandbox network error: {error_msg}. "
                        f"The tool '{tool_name}' failed due to network connectivity issues inside the Docker container. "
                        f"This may be due to: (1) DNS resolution failure, (2) External network not accessible, "
                        f"(3) Firewall/proxy blocking connections. Try using host network mode (STRIX_USE_HOST_NETWORK=true)."
                    )
                raise RuntimeError(f"Sandbox execution error: {error_msg}")
            return response_data.get("result")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise RuntimeError("Authentication failed: Invalid or missing sandbox token") from e
            raise RuntimeError(f"HTTP error calling tool server: {e.response.status_code}") from e
        except httpx.RequestError as e:
            error_str = str(e)
            # Provide more helpful error messages for common issues
            if "connect" in error_str.lower() or "refused" in error_str.lower():
                raise RuntimeError(
                    f"Cannot connect to sandbox tool server at {request_url}. "
                    f"The container may not be running or the tool server hasn't started. "
                    f"Original error: {e}"
                ) from e
            if "timeout" in error_str.lower():
                raise RuntimeError(
                    f"Timeout connecting to sandbox tool server. The tool '{tool_name}' "
                    f"may be hanging or the sandbox is overloaded. "
                    f"Timeout was {SANDBOX_EXECUTION_TIMEOUT}s. Original error: {e}"
                ) from e
            raise RuntimeError(f"Request error calling tool server: {e}") from e
        except httpx.TimeoutException as e:
            raise RuntimeError(
                f"Sandbox execution timed out after {SANDBOX_EXECUTION_TIMEOUT}s. "
                f"The tool '{tool_name}' is taking too long to respond. This may indicate: "
                f"(1) The tool is stuck/hanging, (2) Network congestion, (3) Resource exhaustion in the sandbox. "
                f"Consider interrupting the tool or increasing STRIX_SANDBOX_EXECUTION_TIMEOUT."
            ) from e


async def _execute_tool_locally(tool_name: str, agent_state: Any | None, **kwargs: Any) -> Any:
    tool_func = get_tool_by_name(tool_name)
    if not tool_func:
        raise ValueError(f"Tool '{tool_name}' not found")

    converted_kwargs = convert_arguments(tool_func, kwargs)

    if needs_agent_state(tool_name):
        if agent_state is None:
            raise ValueError(f"Tool '{tool_name}' requires agent_state but none was provided.")
        result = tool_func(agent_state=agent_state, **converted_kwargs)
    else:
        result = tool_func(**converted_kwargs)

    return await result if inspect.isawaitable(result) else result


def validate_tool_availability(tool_name: str | None) -> tuple[bool, str]:
    if tool_name is None:
        return False, "Tool name is missing"

    if tool_name not in get_tool_names():
        return False, f"Tool '{tool_name}' is not available"

    return True, ""


async def execute_tool_with_validation(
    tool_name: str | None, agent_state: Any | None = None, **kwargs: Any
) -> Any:
    is_valid, error_msg = validate_tool_availability(tool_name)
    if not is_valid:
        return f"Error: {error_msg}"

    assert tool_name is not None

    try:
        result = await execute_tool(tool_name, agent_state, **kwargs)
    except Exception as e:  # noqa: BLE001
        error_str = str(e)
        if len(error_str) > 500:
            error_str = error_str[:500] + "... [truncated]"
        return f"Error executing {tool_name}: {error_str}"
    else:
        return result


async def execute_tool_invocation(tool_inv: dict[str, Any], agent_state: Any | None = None) -> Any:
    tool_name = tool_inv.get("toolName")
    tool_args = tool_inv.get("args", {})

    return await execute_tool_with_validation(tool_name, agent_state, **tool_args)


def _check_error_result(result: Any) -> tuple[bool, Any]:
    is_error = False
    error_payload: Any = None

    if (isinstance(result, dict) and "error" in result) or (
        isinstance(result, str) and result.strip().lower().startswith("error:")
    ):
        is_error = True
        error_payload = result

    return is_error, error_payload


def _update_tracer_with_result(
    tracer: Any, execution_id: Any, is_error: bool, result: Any, error_payload: Any
) -> None:
    if not tracer or not execution_id:
        return

    try:
        if is_error:
            tracer.update_tool_execution(execution_id, "error", error_payload)
        else:
            tracer.update_tool_execution(execution_id, "completed", result)
    except (ConnectionError, RuntimeError) as e:
        error_msg = str(e)
        if tracer and execution_id:
            tracer.update_tool_execution(execution_id, "error", error_msg)
        raise


def _format_tool_result(tool_name: str, result: Any) -> tuple[str, list[dict[str, Any]]]:
    images: list[dict[str, Any]] = []

    screenshot_data = extract_screenshot_from_result(result)
    if screenshot_data:
        images.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_data}"},
            }
        )
        result_str = remove_screenshot_from_result(result)
    else:
        result_str = result

    if result_str is None:
        final_result_str = f"Tool {tool_name} executed successfully"
    else:
        final_result_str = str(result_str)
        if len(final_result_str) > 10000:
            start_part = final_result_str[:4000]
            end_part = final_result_str[-4000:]
            final_result_str = start_part + "\n\n... [middle content truncated] ...\n\n" + end_part

    observation_xml = (
        f"<tool_result>\n<tool_name>{tool_name}</tool_name>\n"
        f"<result>{final_result_str}</result>\n</tool_result>"
    )

    return observation_xml, images


async def _execute_single_tool(
    tool_inv: dict[str, Any],
    agent_state: Any | None,
    tracer: Any | None,
    agent_id: str,
) -> tuple[str, list[dict[str, Any]], bool]:
    tool_name = tool_inv.get("toolName", "unknown")
    args = tool_inv.get("args", {})
    execution_id = None
    should_agent_finish = False

    if tracer:
        execution_id = tracer.log_tool_execution_start(agent_id, tool_name, args)

    try:
        result = await execute_tool_invocation(tool_inv, agent_state)

        is_error, error_payload = _check_error_result(result)

        if (
            tool_name in ("finish_scan", "agent_finish")
            and not is_error
            and isinstance(result, dict)
        ):
            if tool_name == "finish_scan":
                should_agent_finish = result.get("scan_completed", False)
            elif tool_name == "agent_finish":
                should_agent_finish = result.get("agent_completed", False)

        _update_tracer_with_result(tracer, execution_id, is_error, result, error_payload)

    except (ConnectionError, RuntimeError, ValueError, TypeError, OSError) as e:
        error_msg = str(e)
        if tracer and execution_id:
            tracer.update_tool_execution(execution_id, "error", error_msg)
        raise

    observation_xml, images = _format_tool_result(tool_name, result)
    return observation_xml, images, should_agent_finish


def _get_tracer_and_agent_id(agent_state: Any | None) -> tuple[Any | None, str]:
    try:
        from strix.telemetry.tracer import get_global_tracer

        tracer = get_global_tracer()
        agent_id = agent_state.agent_id if agent_state else "unknown_agent"
    except (ImportError, AttributeError):
        tracer = None
        agent_id = "unknown_agent"

    return tracer, agent_id


def _can_execute_in_parallel(tool_name: str) -> bool:
    """Check if a tool can be safely executed in parallel with others.
    
    Some tools must be executed sequentially (finish tools, state-modifying tools).
    """
    # Tools that must be executed sequentially
    sequential_tools = {
        "finish_scan",
        "agent_finish",
        "create_agent",
        "wait_for_message",
        "send_message",
    }
    return tool_name not in sequential_tools


async def process_tool_invocations(
    tool_invocations: list[dict[str, Any]],
    conversation_history: list[dict[str, Any]],
    agent_state: Any | None = None,
) -> bool:
    """Process tool invocations with support for parallel execution.
    
    Multi-Action Support:
    - Up to 7 tool invocations can be processed per call for efficiency
    - Independent tools are executed in parallel when possible
    - Sequential tools (finish_scan, agent_finish, etc.) are executed in order
    """
    import asyncio
    
    observation_parts: list[str] = []
    all_images: list[dict[str, Any]] = []
    should_agent_finish = False

    tracer, agent_id = _get_tracer_and_agent_id(agent_state)
    
    # Limit to 7 actions per call (multi-action cap)
    MAX_ACTIONS_PER_CALL = 7
    tool_invocations = tool_invocations[:MAX_ACTIONS_PER_CALL]
    
    # Separate parallel-safe and sequential tools
    parallel_tools = []
    sequential_tools = []
    
    for tool_inv in tool_invocations:
        tool_name = tool_inv.get("toolName", "unknown")
        if _can_execute_in_parallel(tool_name):
            parallel_tools.append(tool_inv)
        else:
            sequential_tools.append(tool_inv)
    
    # Execute parallel-safe tools concurrently
    if parallel_tools:
        async def execute_with_index(idx: int, tool_inv: dict[str, Any]) -> tuple[int, str, list, bool]:
            obs, imgs, finish = await _execute_single_tool(tool_inv, agent_state, tracer, agent_id)
            return (idx, obs, imgs, finish)
        
        tasks = [
            execute_with_index(i, tool_inv) 
            for i, tool_inv in enumerate(parallel_tools)
        ]
        
        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Sort by original index to maintain order in output
        sorted_results = []
        for result in results:
            if isinstance(result, Exception):
                # Handle exceptions gracefully
                sorted_results.append((
                    len(sorted_results),
                    f"<tool_result>\n<tool_name>error</tool_name>\n<result>Error: {result}</result>\n</tool_result>",
                    [],
                    False
                ))
            else:
                sorted_results.append(result)
        
        sorted_results.sort(key=lambda x: x[0])
        
        for _, observation_xml, images, tool_should_finish in sorted_results:
            observation_parts.append(observation_xml)
            all_images.extend(images)
            if tool_should_finish:
                should_agent_finish = True
    
    # Execute sequential tools one by one
    for tool_inv in sequential_tools:
        observation_xml, images, tool_should_finish = await _execute_single_tool(
            tool_inv, agent_state, tracer, agent_id
        )
        observation_parts.append(observation_xml)
        all_images.extend(images)

        if tool_should_finish:
            should_agent_finish = True
            # Stop processing if finish tool was called
            break

    if all_images:
        content = [{"type": "text", "text": "Tool Results:\n\n" + "\n\n".join(observation_parts)}]
        content.extend(all_images)
        conversation_history.append({"role": "user", "content": content})
    else:
        observation_content = "Tool Results:\n\n" + "\n\n".join(observation_parts)
        conversation_history.append({"role": "user", "content": observation_content})

    return should_agent_finish


def extract_screenshot_from_result(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None

    screenshot = result.get("screenshot")
    if isinstance(screenshot, str) and screenshot:
        return screenshot

    return None


def remove_screenshot_from_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    result_copy = result.copy()
    if "screenshot" in result_copy:
        result_copy["screenshot"] = "[Image data extracted - see attached image]"

    return result_copy
