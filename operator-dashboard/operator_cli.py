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
import threading

# Configuration
IDENTITY_PATH = os.environ.get("ZITI_OPERATOR_IDENTITY", "/ziti-config/operator.json")
# Default services; can be overridden via env or CLI
DEFAULT_EXEC_SERVICE = os.environ.get("OPS_EXEC_SERVICE", "ops.exec")
DEFAULT_FILES_SERVICE = os.environ.get("OPS_FILES_SERVICE", "ops.files")
DEFAULT_FORWARD_SERVICE = os.environ.get("OPS_FORWARD_SERVICE", "ops.forward")
RECV_BUFFER = 65536  # 64KB


def log(msg: str):
    """Print log message to stderr."""
    print(f"[operator-cli] {msg}", file=sys.stderr)


def execute_command(cmd: str, args: List[str], service: str) -> dict:
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

    log(f"dialing service: {service}")

    # Create a Ziti socket (service-based addressing uses (service_name, arbitrary_port))
    try:
        sock = openziti.socket(type=socket.SOCK_STREAM)
        port = 65535  # arbitrary placeholder per SDK examples
        sock.connect((service, port))
    except Exception as e:
        log(f"❌ failed to connect to service '{service}': {e}")
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
        print("  operator_cli.py upload <local_path> <remote_path>", file=sys.stderr)
        print("  operator_cli.py download <remote_path> <local_path>", file=sys.stderr)
        print("  operator_cli.py forward <remote_host:port> <local_port>", file=sys.stderr)
        sys.exit(1)
    
    # Parse command and arguments
    cmd = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    log(f"executing: {cmd} {' '.join(args)}")
    
    # Choose service and perform action. Support a simple file upload command:
    #   operator_cli.py upload <local_path> <remote_path>
    if cmd == "upload":
        # file upload via ops.files
        if len(args) < 2:
            print("Usage: operator_cli.py upload <local_path> <remote_path>", file=sys.stderr)
            sys.exit(1)
        local_path = args[0]
        remote_path = args[1]
        # Normalize remote path: disallow absolute paths from operator side by
        # converting a leading '/' into a relative path. The agent will still
        # enforce directory traversal rules server-side.
        if remote_path.startswith("/"):
            remote_path = remote_path.lstrip("/")
        service = os.environ.get("OPS_FILES_SERVICE", DEFAULT_FILES_SERVICE)
        # Read and base64-encode the file
        try:
            with open(local_path, "rb") as f:
                data = f.read()
        except Exception as e:
            log(f"❌ failed to read local file '{local_path}': {e}")
            sys.exit(1)
        import base64
        payload = {"op": "upload", "path": remote_path, "data": base64.b64encode(data).decode("ascii"), "caller": os.environ.get("ZITI_IDENTITY_NAME") or os.path.splitext(os.path.basename(IDENTITY_PATH))[0]}

        # send via same socket logic
        response = None
        try:
            openziti.load(IDENTITY_PATH)
        except Exception as e:
            log(f"❌ failed to load identity: {e}")
            response = {"ok": False, "error": "identity_load_error", "message": str(e)}

        if response is None:
            sock = None
            try:
                sock = openziti.socket(type=socket.SOCK_STREAM)
                sock.connect((service, 65535))
                sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
                # read single-line response
                chunks = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    if b"\n" in chunk:
                        break
                raw = b"".join(chunks)
                nl = raw.find(b"\n")
                if nl != -1:
                    raw = raw[:nl]
                response = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception as e:
                log(f"❌ upload failed: {e}")
                response = {"ok": False, "error": "upload_error", "message": str(e)}
            finally:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass

    elif cmd == "download":
        # download: operator_cli.py download <remote_path> <local_path>
        if len(args) < 2:
            print("Usage: operator_cli.py download <remote_path> <local_path>", file=sys.stderr)
            sys.exit(1)
        remote_path = args[0]
        local_path = args[1]
        # normalize remote path
        if remote_path.startswith("/"):
            remote_path = remote_path.lstrip("/")

        service = os.environ.get("OPS_FILES_SERVICE", DEFAULT_FILES_SERVICE)
        payload = {"op": "download", "path": remote_path, "caller": os.environ.get("ZITI_IDENTITY_NAME") or os.path.splitext(os.path.basename(IDENTITY_PATH))[0]}

        sock = None
        try:
            try:
                openziti.load(IDENTITY_PATH)
            except Exception as e:
                log(f"❌ failed to load identity: {e}")
                sys.exit(1)

            sock = openziti.socket(type=socket.SOCK_STREAM)
            sock.connect((service, 65535))
            sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))

            # Read single-line JSON response
            chunks = []
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
            raw = b"".join(chunks)
            nl = raw.find(b"\n")
            if nl != -1:
                raw = raw[:nl]
            response = json.loads(raw.decode("utf-8", errors="replace"))

            if not response.get("ok"):
                log(f"❌ download failed: {response.get('error')} {response.get('message','')}")
            else:
                data_b64 = response.get("data")
                if data_b64 is None:
                    log("❌ download response missing data field")
                    response = {"ok": False, "error": "missing_data", "message": "no data in response"}
                else:
                    import base64
                    try:
                        data = base64.b64decode(data_b64)
                        # write to local_path
                        with open(local_path, "wb") as f:
                            f.write(data)
                        log(f"✅ downloaded {response.get('path')} -> {local_path} (size={len(data)})")
                    except Exception as e:
                        log(f"❌ failed to write local file: {e}")
                        response = {"ok": False, "error": "write_error", "message": str(e)}

        except Exception as e:
            log(f"❌ download failed: {e}")
            response = {"ok": False, "error": "download_error", "message": str(e)}
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    elif cmd == "forward":
        # operator_cli.py forward <remote_host:port> <local_port>
        if len(args) < 2:
            print("Usage: operator_cli.py forward <remote_host:port> <local_port>", file=sys.stderr)
            sys.exit(1)
        remote_target = args[0]
        local_port = args[1]
        # Start forwarding (blocks until Ctrl+C)
        service = os.environ.get("OPS_FORWARD_SERVICE", DEFAULT_FORWARD_SERVICE)
        forward_server(remote_target, int(local_port), service)
        return

    else:
        # default: execute command via ops.exec
        service = os.environ.get("OPS_EXEC_SERVICE", DEFAULT_EXEC_SERVICE)
        response = execute_command(cmd, args, service)

    # Format and print the response
    print(format_response(response))

    # Exit with the remote command's exit code if available
    if response.get("ok") and "exit_code" in response:
        sys.exit(response["exit_code"])
    elif not response.get("ok"):
        sys.exit(1)


def forward_server(remote_target: str, local_port: int, service: str = DEFAULT_FORWARD_SERVICE):
    """Listen on localhost:`local_port` and forward each connection to `remote_target`
    via the given Ziti `service` (ops.forward)."""

    caller = os.environ.get("ZITI_IDENTITY_NAME") or os.path.splitext(os.path.basename(IDENTITY_PATH))[0]

    # Ensure identity loaded once
    try:
        openziti.load(IDENTITY_PATH)
    except Exception as e:
        log(f"❌ failed to load identity for forwarding: {e}")
        return

    bind_addr = os.environ.get("OPS_FORWARD_BIND_ADDR", "0.0.0.0")
    listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen_sock.bind((bind_addr, int(local_port)))
    listen_sock.listen(5)
    log(f"Forwarding: local {bind_addr}:{local_port} -> remote {remote_target} via service {service}")

    def handle_client(client_sock, addr):
        ziti_sock = None
        try:
            ziti_sock = openziti.socket(type=socket.SOCK_STREAM)
            ziti_sock.connect((service, 65535))

            # Use a raw TCP tunnel — do not send a JSON header.
            # The agent expects a raw TCP stream and will connect to its configured target.

            # Relay bytes between client_sock and ziti_sock
            def relay(src, dst):
                try:
                    while True:
                        data = src.recv(RECV_BUFFER)
                        # openziti socket wrappers may return (data, meta) tuples — normalize.
                        if isinstance(data, (tuple, list)) and len(data) > 0:
                            data = data[0]
                        if not data:
                            break
                        dst.sendall(data)
                except Exception:
                    pass
                finally:
                    try:
                        dst.shutdown(socket.SHUT_WR)
                    except Exception:
                        pass

            t1 = threading.Thread(target=relay, args=(client_sock, ziti_sock), daemon=True)
            t2 = threading.Thread(target=relay, args=(ziti_sock, client_sock), daemon=True)
            t1.start(); t2.start()
            t1.join(); t2.join()

        except Exception as e:
            log(f"❌ forward connection error: {e}")
        finally:
            try:
                if ziti_sock:
                    ziti_sock.close()
            except Exception:
                pass
            try:
                client_sock.close()
            except Exception:
                pass

    try:
        while True:
            client, addr = listen_sock.accept()
            t = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log("Stopping forward server")
    finally:
        try:
            listen_sock.close()
        except Exception:
            pass
    
    


if __name__ == "__main__":
    main()
