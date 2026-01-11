import os
import sys
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Set dummy token for testing if not set
os.environ["STRIX_SERVER_TOKEN"] = "test-token"

# Mock tool initialization to avoid slow imports
with patch("strix.tools.registry.get_tool_names", return_value=["test_tool"]):
    from strix.runtime.remote_tool_server.http_server import app

client = TestClient(app)

def run_test(name, func):
    print(f"Running {name}...", end=" ", flush=True)
    try:
        func()
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

def test_health_get():
    # Mock network check to avoid hang
    with patch("socket.gethostbyname", side_effect=Exception("No network")):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["network_status"] == "disconnected"

def test_health_post():
    response = client.post("/health")
    assert response.status_code == 200
    assert response.json()["healthy"] is True

def test_execute_unauthorized():
    response = client.post("/execute", json={
        "tool_name": "test_tool",
        "kwargs": {},
        "auth_token": "wrong-token"
    })
    assert response.status_code == 401

def test_execute_success():
    # Mocking the executor
    mock_executor = MagicMock()
    mock_executor.execute_tool.return_value = {"result": "success_result"}
    
    with patch("strix.runtime.remote_tool_server.http_server.get_tool_executor", return_value=mock_executor):
        response = client.post("/execute", json={
            "tool_name": "test_tool",
            "kwargs": {"arg1": "val1"},
            "auth_token": "test-token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"] == "success_result"
        mock_executor.execute_tool.assert_called_once_with("test_tool", {"arg1": "val1"}, timeout=None)

def test_execute_with_timeout():
    mock_executor = MagicMock()
    mock_executor.execute_tool.return_value = {"result": "timeout_result"}
    
    with patch("strix.runtime.remote_tool_server.http_server.get_tool_executor", return_value=mock_executor):
        response = client.post("/execute", json={
            "tool_name": "test_tool",
            "kwargs": {},
            "timeout": 10.5,
            "auth_token": "test-token"
        })
        
        assert response.status_code == 200
        mock_executor.execute_tool.assert_called_once_with("test_tool", {}, timeout=10.5)

def test_execute_error():
    mock_executor = MagicMock()
    mock_executor.execute_tool.return_value = {"error": "some_error"}
    
    with patch("strix.runtime.remote_tool_server.http_server.get_tool_executor", return_value=mock_executor):
        response = client.post("/execute", json={
            "tool_name": "test_tool",
            "kwargs": {},
            "auth_token": "test-token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "some_error"
        assert data["exit_code"] == 1

def test_execute_batch():
    mock_executor = MagicMock()
    mock_executor.execute_batch.return_value = [
        {"result": "res1"},
        {"error": "err2"}
    ]
    
    with patch("strix.runtime.remote_tool_server.http_server.get_tool_executor", return_value=mock_executor):
        response = client.post("/execute_batch", json={
            "tools": [
                {"tool_name": "t1", "kwargs": {}},
                {"tool_name": "t2", "kwargs": {}}
            ],
            "auth_token": "test-token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 2
        assert data["results"][0]["success"] is True
        assert data["results"][0]["result"] == "res1"
        assert data["results"][1]["success"] is False
        assert data["results"][1]["error"] == "err2"

def test_register_agent():
    response = client.post("/register_agent", json={
        "agent_id": "agent-123",
        "auth_token": "test-token"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["agent_id"] == "agent-123"

def main():
    print("=== FASTAPI SERVER VERIFICATION ===")
    run_test("test_health_get", test_health_get)
    run_test("test_health_post", test_health_post)
    run_test("test_execute_unauthorized", test_execute_unauthorized)
    run_test("test_execute_success", test_execute_success)
    run_test("test_execute_with_timeout", test_execute_with_timeout)
    run_test("test_execute_error", test_execute_error)
    run_test("test_execute_batch", test_execute_batch)
    run_test("test_register_agent", test_register_agent)

if __name__ == "__main__":
    main()
