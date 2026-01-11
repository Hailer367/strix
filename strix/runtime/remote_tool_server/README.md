# Strix Remote Tool Server

This package implements a gRPC-based remote tool server that allows Strix agents to execute tools on a remote server instead of inside Docker containers. This eliminates Docker networking issues and provides full system access.

## Architecture

- **gRPC Server**: Exposes all Strix tools via gRPC protocol
- **Cloudflared Tunnel**: Provides public access to the server
- **GitHub Secrets**: Stores connection credentials (CRED_TUNNEL, STRIX_SERVER_TOKEN)

## Components

### Server (`server.py`)
Main gRPC server that handles tool execution requests.

### Tool Executor (`tool_executor.py`)
Executes tools with concurrent support using thread pools.

### gRPC Client (`grpc_client.py`)
Client wrapper for making gRPC calls to the remote server.

### StrixDB Client (`strixdb_client.py`)
Handles artifact persistence to StrixDB repository.

### Proto Files (`proto/`)
gRPC service definitions and generated code.

## Usage

### Starting the Server

1. Run the `strix-server.yml` GitHub Actions workflow
2. The workflow will:
   - Generate gRPC proto files
   - Start the gRPC server
   - Create cloudflared tunnel
   - Update CRED_TUNNEL and STRIX_SERVER_TOKEN secrets

### Connecting from Agent

The agent workflow (`strixer.yml`) automatically detects the remote server if:
- `CRED_TUNNEL` secret is set
- `STRIX_SERVER_TOKEN` secret is set

The runtime factory will automatically use `RemoteRuntime` instead of `DockerRuntime`.

## Environment Variables

- `STRIX_SERVER_PORT`: Server port (default: 50051)
- `STRIX_SERVER_TOKEN`: Authentication token
- `STRIX_TOOL_POOL_SIZE`: Thread pool size (default: 10)
- `STRIXDB_TOKEN`: GitHub token for StrixDB access
- `CRED_TUNNEL`: Cloudflared tunnel URL (set by server workflow)

## Generating Proto Files

To generate gRPC code from proto files:

```bash
python -m strix.runtime.remote_tool_server.generate_proto
```

This creates:
- `proto/tool_service_pb2.py` - Message classes
- `proto/tool_service_pb2_grpc.py` - Service stubs

## Updating Secrets

To update GitHub secrets programmatically:

```bash
python -m strix.runtime.remote_tool_server.update_secret \
  <GITHUB_TOKEN> \
  <OWNER> \
  <REPO> \
  <SECRET_NAME> \
  <SECRET_VALUE>
```

## Benefits

- **No Docker Networking Issues**: Direct system access
- **Full Root Access**: Install any tools needed
- **Better Performance**: gRPC is faster than HTTP
- **Persistent Artifacts**: StrixDB integration
- **Scalable**: Handles multiple concurrent agents
