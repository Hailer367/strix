"""Script to generate gRPC code from proto files."""

import subprocess
import sys
from pathlib import Path

# Get the directory containing this script
SCRIPT_DIR = Path(__file__).parent
PROTO_DIR = SCRIPT_DIR / "proto"
PROTO_FILE = PROTO_DIR / "tool_service.proto"


def generate_grpc_code() -> None:
    """Generate Python gRPC code from proto file."""
    if not PROTO_FILE.exists():
        print(f"Error: Proto file not found at {PROTO_FILE}")
        sys.exit(1)

    print(f"Generating gRPC code from {PROTO_FILE}...")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "grpc_tools.protoc",
                f"--python_out={PROTO_DIR}",
                f"--grpc_python_out={PROTO_DIR}",
                f"--proto_path={PROTO_DIR}",
                str(PROTO_FILE),
            ],
            check=True,
        )
        print("✓ gRPC code generated successfully")
        print(f"  Generated files in {PROTO_DIR}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating gRPC code: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: grpc_tools.protoc not found. Install grpcio-tools:")
        print("  pip install grpcio-tools")
        sys.exit(1)


if __name__ == "__main__":
    generate_grpc_code()
