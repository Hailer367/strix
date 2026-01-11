import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# Simulate a minimal test runner
async def run_test(name, func):
    print(f"Running {name}...", end=" ", flush=True)
    try:
        if asyncio.iscoroutinefunction(func):
            await func()
        else:
            func()
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

# Test timeout configuration
def test_timeout_config():
    # Test http_client
    with patch.dict(os.environ, {"STRIX_TOOL_TIMEOUT": "500.0"}):
        import importlib
        import strix.runtime.remote_tool_server.http_client as http_client
        importlib.reload(http_client)
        assert http_client.DEFAULT_TIMEOUT == 500.0
    
    # Test tool_executor
    with patch.dict(os.environ, {"STRIX_TOOL_EXECUTION_TIMEOUT": "400.0"}):
        import strix.runtime.remote_tool_server.tool_executor as tool_executor
        importlib.reload(tool_executor)
        assert tool_executor.TOOL_EXECUTION_TIMEOUT == 400.0

# Test background execution logic
async def test_background_tool_execution():
    from strix.tools.executor import _execute_single_tool
    
    tool_inv = {
        "toolName": "terminal_execute",
        "args": {"command": "sleep 10", "background": True}
    }
    
    agent_state = MagicMock()
    agent_state.agent_id = "test_agent"
    tracer = MagicMock()
    
    # Mock execute_tool_invocation to return something after a delay
    with patch("strix.tools.executor.execute_tool_invocation", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = {"content": "Finished sleep", "status": "success"}
        
        # We also need to mock _agent_messages from agents_graph_actions
        with patch("strix.tools.agents_graph.agents_graph_actions._agent_messages", {}) as mock_messages:
            
            obs_xml, images, should_finish = await _execute_single_tool(
                tool_inv, agent_state, tracer, "test_agent"
            )
            
            # Should return immediately with a background notice
            assert "Tool started in background" in obs_xml
            assert images == []
            assert should_finish is False
            
            # Give it a tiny bit to start the task
            await asyncio.sleep(0.5)
            
            # Check if a message was "sent" back to the agent
            assert "test_agent" in mock_messages
            assert len(mock_messages["test_agent"]) == 1
            assert "Background tool completion notice" in mock_messages["test_agent"][0]["content"]
            assert "Finished sleep" in mock_messages["test_agent"][0]["content"]

# Test per-tool timeout logic
async def test_per_tool_timeout():
    from strix.tools.executor import _execute_single_tool
    
    # Test local execution timeout
    tool_inv = {
        "toolName": "terminal_execute",
        "args": {"command": "sleep 10", "timeout": 0.1}
    }
    
    agent_state = MagicMock()
    agent_state.agent_id = "test_agent"
    tracer = MagicMock()
    
    # Mock execute_tool_invocation to simulate a timeout if it were real, 
    # but here we just want to verify the timeout is passed.
    with patch("strix.tools.executor.execute_tool_invocation", new_callable=AsyncMock) as mock_inv:
        await _execute_single_tool(tool_inv, agent_state, tracer, "test_agent")
        # Verify timeout=0.1 was passed to execute_tool_invocation
        args, kwargs = mock_inv.call_args
        assert kwargs["timeout"] == 0.1

async def main():
    print("=== ASYNC TOOLS & TIMEOUT VERIFICATION ===")
    await run_test("test_timeout_config", test_timeout_config)
    await run_test("test_background_tool_execution", test_background_tool_execution)
    await run_test("test_per_tool_timeout", test_per_tool_timeout)

if __name__ == "__main__":
    asyncio.run(main())
