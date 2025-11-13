#!/usr/bin/env python3
"""
Operator CLI - Dials the ops.exec service to execute commands on edge devices.

Usage:
    python operator_cli.py <command> [args...]
    
Examples:
    python operator_cli.py uname -a
    python operator_cli.py ls -la /app
    python operator_cli.py uptime
"""
import json
import os
import sys
from typing import List

# Third-party
import openziti # type: ignore
import socket

# Configuration
IDENTITY_PATH = os.environ.get("ZITI_OPERATOR_IDENTITY", "/ziti-config/operator.json")
SERVICE_NAME = os.environ.get("OPS_EXEC_SERVICE", "ops.exec")
RECV_BUFFER = 65536  # 64KB


def log(msg: str):
    """Print log message to stderr."""
    print(f"[operator-cli] {msg}", file=sys.stderr)


def execute_command(cmd: str, args: List[str]) -> dict:
    """
    Execute a command on the edge device via ops.exec service.
    
    Args:
        cmd: Command name (e.g., "uname", "ls")
        args: Command arguments (e.g., ["-a"], ["-la", "/app"])
    
    Returns:
        dict: Response from edge agent with keys: ok, exit_code, stdout, stderr, duration_ms
              or error response: ok=False, error, message
    """
    log(f"loading identity: {IDENTITY_PATH}")

    # Initialize Ziti context; required before creating sockets in 1.4.x
    try:
        openziti.load(IDENTITY_PATH)
    except Exception as e:
        log(f"❌ failed to load identity: {e}")
        return {"ok": False, "error": "identity_load_error", "message": str(e)}

    log(f"dialing service: {SERVICE_NAME}")

    # Create a Ziti socket (service-based addressing uses (service_name, arbitrary_port))
    try:
        sock = openziti.socket(type=socket.SOCK_STREAM)
        port = 65535  # arbitrary placeholder per SDK examples
        sock.connect((SERVICE_NAME, port))
    except Exception as e:
        log(f"❌ failed to connect to service '{SERVICE_NAME}': {e}")
        return {"ok": False, "error": "connection_error", "message": str(e)}
    
    try:
        # Send the command request (include best-effort caller identifier)
        caller = os.environ.get("ZITI_IDENTITY_NAME") or os.path.splitext(os.path.basename(IDENTITY_PATH))[0]
        request = {"cmd": cmd, "args": args, "caller": caller}
        request_json = json.dumps(request) + "\n"
        log(f"sending: {request}")
        sock.sendall(request_json.encode("utf-8"))

        # Receive a single line-delimited JSON response (harden framing)
        try:
            sock.settimeout(30)
        except Exception:
            pass

        chunks = []
        total = 0
        max_bytes = 1024 * 1024  # 1MB safety cap
        found_nl = False
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if b"\n" in chunk:
                found_nl = True
                break
            if total >= max_bytes:
                log("⚠️ response too large; truncating")
                break

        raw = b"".join(chunks)
        nl_idx = raw.find(b"\n")
        if nl_idx != -1:
            raw = raw[:nl_idx]
        response_data = raw.decode("utf-8", errors="replace")

        if not response_data:
            log("⚠️ received empty response from service")
            return {"ok": False, "error": "empty_response", "message": "No data received from service"}

        # Parse JSON response
        try:
            response = json.loads(response_data.strip())
            return response
        except json.JSONDecodeError as e:
            log(f"⚠️ failed to parse JSON response: {e}")
            return {"ok": False, "error": "json_parse_error", "message": str(e), "raw": response_data}

    except Exception as e:
        log(f"❌ error during command execution: {e}")
        return {"ok": False, "error": "execution_error", "message": str(e)}

    finally:
        sock.close()


def format_response(response: dict) -> str:
    """Format the response for display."""
    output = []
    
    if response.get("ok"):
        # Success case
        exit_code = response.get("exit_code", -1)
        duration = response.get("duration_ms", 0)
        
        output.append(f"✅ Command executed successfully (exit code: {exit_code}, duration: {duration}ms)")
        
        stdout = response.get("stdout", "")
        stderr = response.get("stderr", "")
        
        if stdout:
            output.append("\n📤 STDOUT:")
            output.append(stdout.rstrip())
        
        if stderr:
            output.append("\n⚠️ STDERR:")
            output.append(stderr.rstrip())
        
        if not stdout and not stderr:
            output.append("(no output)")
    
    else:
        # Error case
        error = response.get("error", "unknown")
        message = response.get("message", "No error message")
        
        output.append(f"❌ Command failed: {error}")
        output.append(f"   {message}")
        
        # Include any available output
        stdout = response.get("stdout", "")
        stderr = response.get("stderr", "")
        
        if stdout:
            output.append("\n📤 STDOUT (partial):")
            output.append(stdout.rstrip())
        
        if stderr:
            output.append("\n⚠️ STDERR (partial):")
            output.append(stderr.rstrip())
    
    return "\n".join(output)


def main():
    if len(sys.argv) < 2:
        print("Usage: operator_cli.py <command> [args...]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  operator_cli.py uname -a", file=sys.stderr)
        print("  operator_cli.py ls -la /app", file=sys.stderr)
        print("  operator_cli.py uptime", file=sys.stderr)
        print("  operator_cli.py echo 'Hello from operator'", file=sys.stderr)
        sys.exit(1)
    
    # Parse command and arguments
    cmd = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    log(f"executing: {cmd} {' '.join(args)}")
    
    # Execute the command
    response = execute_command(cmd, args)
    
    # Format and print the response
    print(format_response(response))
    
    # Exit with the remote command's exit code if available
    if response.get("ok") and "exit_code" in response:
        sys.exit(response["exit_code"])
    elif not response.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
