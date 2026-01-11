"""Tool execution engine for remote tool server."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from strix.tools.argument_parser import ArgumentConversionError, convert_arguments
from strix.tools.registry import get_tool_by_name

logger = logging.getLogger(__name__)

# Default thread pool size for concurrent execution
DEFAULT_POOL_SIZE = 10
TOOL_EXECUTION_TIMEOUT = 60.0  # seconds


class ToolExecutor:
    """Executes Strix tools with concurrent support."""

    def __init__(self, pool_size: int = DEFAULT_POOL_SIZE) -> None:
        """Initialize tool executor with thread pool."""
        self.executor = ThreadPoolExecutor(
            max_workers=pool_size, thread_name_prefix="strix-tool-"
        )
        self._tools_initialized = False
        self._initialize_tools()

    def _initialize_tools(self) -> None:
        """Pre-import tool modules for faster execution."""
        if self._tools_initialized:
            return

        try:
            # Import tool registry to ensure all tools are loaded
            from strix.tools.registry import get_tool_names

            tool_count = len(get_tool_names())
            logger.info(f"Initialized {tool_count} tools in remote tool server")
            self._tools_initialized = True
        except Exception as e:
            logger.warning(f"Failed to pre-initialize tools: {e}")

    def execute_tool(
        self, tool_name: str, kwargs: dict[str, Any], agent_state: Any | None = None
    ) -> dict[str, Any]:
        """Execute a single tool synchronously.

        Args:
            tool_name: Name of the tool to execute
            kwargs: Tool arguments (already converted from JSON)
            agent_state: Optional agent state (for tools that need it)

        Returns:
            Dictionary with result or error
        """
        try:
            tool_func = get_tool_by_name(tool_name)
            if not tool_func:
                return {"error": f"Tool '{tool_name}' not found"}

            # Convert arguments to proper types
            try:
                converted_kwargs = convert_arguments(tool_func, kwargs)
            except Exception as e:
                return {"error": f"Argument conversion error: {str(e)}"}

            # Check if tool needs agent_state
            from strix.tools.registry import needs_agent_state

            if needs_agent_state(tool_name):
                if agent_state is None:
                    # Create a minimal agent_state object for tools that need it
                    # This allows tools to execute even without full agent context
                    class MinimalAgentState:
                        def __init__(self) -> None:
                            self.agent_id = "remote-server-agent"
                            self.sandbox_id = "remote-server"
                            self.sandbox_token = ""
                            self.sandbox_info = {}
                    
                    agent_state = MinimalAgentState()
                result = tool_func(agent_state=agent_state, **converted_kwargs)
            else:
                result = tool_func(**converted_kwargs)

            # Handle async results
            import inspect

            if inspect.isawaitable(result):
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(result)
                finally:
                    loop.close()

            return {"result": result}

        except ArgumentConversionError as e:
            return {"error": f"Invalid arguments: {e}"}
        except Exception as e:
            logger.exception(f"Tool execution error for {tool_name}")
            return {"error": f"Tool execution error: {type(e).__name__}: {str(e)}"}

    def execute_batch(
        self,
        tools: list[dict[str, Any]],
        agent_state: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Execute multiple tools concurrently.

        Args:
            tools: List of tool specifications with 'tool_name' and 'kwargs'
            agent_state: Optional agent state

        Returns:
            List of execution results
        """
        import concurrent.futures

        results = []

        def execute_single(spec: dict[str, Any]) -> dict[str, Any]:
            tool_name = spec.get("tool_name", "")
            kwargs = spec.get("kwargs", {})
            return self.execute_tool(tool_name, kwargs, agent_state)

        # Execute all tools concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tools)) as executor:
            futures = [executor.submit(execute_single, tool_spec) for tool_spec in tools]
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result(timeout=TOOL_EXECUTION_TIMEOUT))
                except Exception as e:
                    results.append({"error": f"Execution error: {e}"})

        return results

    def shutdown(self) -> None:
        """Shutdown the executor and cleanup resources."""
        if self.executor:
            logger.info("Shutting down tool executor...")
            self.executor.shutdown(wait=True, cancel_futures=True)
