#!/usr/bin/env python3
import json
import os
import signal
import socketserver
import socket
import subprocess
import sys
import threading
import time
import atexit
from typing import List
import base64
import hashlib

# Third-party
import openziti # type: ignore

# Configuration
IDENTITY_PATH = os.environ.get("ZITI_EDGE_IDENTITY", "/ziti-config/edge-device.json")
OPS_EXEC_SERVICE = os.environ.get("OPS_EXEC_SERVICE", "ops.exec")
OPS_FILES_SERVICE = os.environ.get("OPS_FILES_SERVICE", "ops.files")
BIND_ADDR = os.environ.get("OPS_BIND_ADDR", "0.0.0.0")
OPS_EXEC_BIND_PORT = int(os.environ.get("OPS_EXEC_BIND_PORT", "5555"))
OPS_FILES_BIND_PORT = int(os.environ.get("OPS_FILES_BIND_PORT", "5556"))
OPS_FORWARD_SERVICE = os.environ.get("OPS_FORWARD_SERVICE", "ops.forward")
OPS_FORWARD_BIND_PORT = int(os.environ.get("OPS_FORWARD_BIND_PORT", "5557"))
# Comma-separated list of allowed forward hosts (default: localhost only)
OPS_FORWARD_ALLOWED_HOSTS = [h.strip() for h in os.environ.get("OPS_FORWARD_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
# Comma-separated list of allowed forward ports (default common HTTP/SSH/VNC ports)
OPS_FORWARD_ALLOWED_PORTS = [int(p.strip()) for p in os.environ.get("OPS_FORWARD_ALLOWED_PORTS", "22,80,443,8080,5900").split(",") if p.strip()]
# Default fixed target for raw forwarding (can be overridden via env)
OPS_FORWARD_DEFAULT_TARGET_HOST = os.environ.get("OPS_FORWARD_DEFAULT_TARGET_HOST", "127.0.0.1")
OPS_FORWARD_DEFAULT_TARGET_PORT = int(os.environ.get("OPS_FORWARD_DEFAULT_TARGET_PORT", "8080"))
TIMEOUT_SECS = int(os.environ.get("OPS_EXEC_TIMEOUT_SECONDS", "30"))
OPS_FILES_BASE_DIR = os.environ.get("OPS_FILES_BASE_DIR", "/var/local/ops_files")

# Simple, safe default allowlist. Override with OPS_EXEC_ALLOWLIST="ls,uname,uptime,whoami,echo"
DEFAULT_ALLOWLIST = ["ls", "uname", "whoami", "echo"]
ALLOWLIST: List[str] = [c.strip() for c in os.environ.get("OPS_EXEC_ALLOWLIST", ",".join(DEFAULT_ALLOWLIST)).split(",") if c.strip()]

MAX_OUTPUT_CHARS = int(os.environ.get("OPS_EXEC_MAX_OUTPUT", "100000"))  # 100KB


def log(msg: str):
    print(f"[edge-agent][ops.exec] {msg}")


def _safe_join(base: str, rel_path: str) -> str:
    base = os.path.abspath(base)
    target = os.path.normpath(os.path.join(base, rel_path))
    if not target.startswith(base + os.sep) and target != base:
        raise ValueError("path outside base directory")
    return target


def validate_command(cmd: str, args: List[str]) -> str:
    """Validate command against allowlist and basic safety rules.

    Returns the resolved base command to execute.
    Raises ValueError on invalid input.
    """
    if not cmd or not isinstance(cmd, str):
        raise ValueError("cmd must be a non-empty string")

    # Only allow bare command names, no paths
    base = os.path.basename(cmd)
    if base != cmd:
        raise ValueError("cmd must be a bare command name (no paths)")

    # Enforce allowlist
    if base not in ALLOWLIST:
        raise ValueError(f"command '{base}' not permitted")

    # Basic arg hygiene
    if args is None:
        args = []
    if not isinstance(args, list):
        raise ValueError("args must be a list of strings")

    for a in args:
        if not isinstance(a, str):
            raise ValueError("all args must be strings")
        # Disallow null bytes and excessive length
        if "\x00" in a or len(a) > 4096:
            raise ValueError("invalid argument value")

    return base


def run_command(cmd: str, args: List[str]):
    start = time.time()
    try:
        proc = subprocess.run(
            [cmd, *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS,
            check=False,
        )
        duration_ms = int((time.time() - start) * 1000)
        stdout = (proc.stdout or "")[:MAX_OUTPUT_CHARS]
        stderr = (proc.stderr or "")[:MAX_OUTPUT_CHARS]
        return {
            "ok": True,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "error": "timeout",
            "message": f"command exceeded {TIMEOUT_SECS}s",
            "stdout": (e.stdout or "")[:MAX_OUTPUT_CHARS] if hasattr(e, "stdout") else "",
            "stderr": (e.stderr or "")[:MAX_OUTPUT_CHARS] if hasattr(e, "stderr") else "",
            "duration_ms": duration_ms,
        }
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "error": "exec_error",
            "message": str(e),
            "duration_ms": duration_ms,
        }


class FilesRequestHandler(socketserver.StreamRequestHandler):
    """Very small MVP files handler.

    Protocol (single-line JSON):
    - upload: {"op":"upload","path":"rel/path","data":"<base64>", "caller":...}
      server writes file to OPS_FILES_BASE_DIR/rel/path and replies {ok: true, size:, sha256:}
    """

    def handle(self):
        try:
            line = self.rfile.readline()
            if not line:
                self._send({"ok": False, "error": "empty_request"})
                return
            try:
                req = json.loads(line.decode("utf-8"))
            except Exception as e:
                self._send({"ok": False, "error": "bad_json", "message": str(e)})
                return

            op = req.get("op")
            caller = req.get("caller")
            if caller:
                log(f"files caller: {caller}")

            if op == "upload":
                path = req.get("path")
                data_b64 = req.get("data")
                if not path or not data_b64:
                    self._send({"ok": False, "error": "validation", "message": "missing path or data"})
                    return

                try:
                    final_path = _safe_join(OPS_FILES_BASE_DIR, path)
                except ValueError:
                    self._send({"ok": False, "error": "path_forbidden"})
                    return

                os.makedirs(os.path.dirname(final_path), exist_ok=True)
                try:
                    data = base64.b64decode(data_b64)
                except Exception:
                    self._send({"ok": False, "error": "bad_base64"})
                    return

                try:
                    with open(final_path, "wb") as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())
                except Exception as e:
                    self._send({"ok": False, "error": "io_error", "message": str(e)})
                    return

                sha = hashlib.sha256(data).hexdigest()
                self._send({"ok": True, "path": final_path, "size": len(data), "sha256": sha})
                return

            if op == "download":
                path = req.get("path")
                if not path:
                    self._send({"ok": False, "error": "validation", "message": "missing path"})
                    return

                try:
                    final_path = _safe_join(OPS_FILES_BASE_DIR, path)
                except ValueError:
                    self._send({"ok": False, "error": "path_forbidden"})
                    return

                if not os.path.exists(final_path):
                    self._send({"ok": False, "error": "not_found", "message": "file not found"})
                    return

                try:
                    with open(final_path, "rb") as f:
                        data = f.read()
                except Exception as e:
                    self._send({"ok": False, "error": "io_error", "message": str(e)})
                    return

                b64 = base64.b64encode(data).decode("ascii")
                sha = hashlib.sha256(data).hexdigest()
                self._send({"ok": True, "path": final_path, "size": len(data), "data": b64, "sha256": sha})
                return

            else:
                self._send({"ok": False, "error": "unsupported_op", "message": f"op={op}"})
                return

        except Exception as e:
            self._send({"ok": False, "error": "handler_error", "message": str(e)})

    def _send(self, obj):
        payload = (json.dumps(obj) + "\n").encode("utf-8")
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except Exception:
            pass


class ExecRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        try:
            # Read a single line-delimited JSON request
            data = self.rfile.readline()
            if not data:
                self._send({"ok": False, "error": "empty_request"})
                return

            try:
                req = json.loads(data.decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send({"ok": False, "error": "bad_json", "message": str(e)})
                return

            caller = req.get("caller")
            if caller:
                log(f"caller: {caller}")

            cmd = req.get("cmd")
            args = req.get("args", [])

            try:
                base = validate_command(cmd, args)
            except ValueError as ve:
                self._send({"ok": False, "error": "validation", "message": str(ve)})
                return

            log(f"exec: {base} {args} \n")
            result = run_command(base, args)
            self._send(result)
        except Exception as e:
            self._send({"ok": False, "error": "handler_error", "message": str(e)})
        finally:
            try:
                self.request.shutdown(2)
            except Exception:
                pass

    def _send(self, obj):
        payload = (json.dumps(obj) + "\n").encode("utf-8")
        self.wfile.write(payload)
        self.wfile.flush()


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True  # let threads die quickly on shutdown


class ForwardRequestHandler(socketserver.StreamRequestHandler):
    """Port-forwarding handler.

    Protocol (single-line JSON header):
    {"target":"host:port","caller":...}

    After the header is received and validated, the handler opens a local TCP
    connection to the target and relays raw bytes bidirectionally.
    """

    def handle(self):
        # For raw TCP forwarding we do not expect a JSON header from the dialer.
        # Use a fixed target (configurable via env) and simply relay raw bytes.
        caller = None
        try:
            caller = getattr(self.request, 'caller', None)
        except Exception:
            caller = None

        host = OPS_FORWARD_DEFAULT_TARGET_HOST
        port = OPS_FORWARD_DEFAULT_TARGET_PORT

        # Enforce allowed hosts and ports
        if host not in OPS_FORWARD_ALLOWED_HOSTS:
            self._send_error("forbidden", "host not allowed")
            return
        if port not in OPS_FORWARD_ALLOWED_PORTS:
            self._send_error("forbidden", "port not allowed")
            return

        log(f"forward caller: {caller or 'unknown'} target: {host}:{port}")

        try:
            # Use explicit socket connect to avoid monkeypatch tuple issues
            local_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local_sock.settimeout(5)
            local_sock.connect((host, port))
        except Exception as e:
            self._send_error("connect_failed", str(e))
            return

        # Relay raw bytes between the Ziti socket (self.request) and local_sock
        def relay(src, dst):
            try:
                while True:
                    data = src.recv(4096)
                    # Normalize potential (data, meta) tuples from wrapped sockets
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

        t1 = threading.Thread(target=relay, args=(self.request, local_sock), name="Fwd-Z2L", daemon=True)
        t2 = threading.Thread(target=relay, args=(local_sock, self.request), name="Fwd-L2Z", daemon=True)
        t1.start(); t2.start()
        t1.join(); t2.join()

        try:
            local_sock.close()
        except Exception:
            pass

    def _send_error(self, code, message=None):
        obj = {"ok": False, "error": code}
        if message:
            obj["message"] = message
        payload = (json.dumps(obj) + "\n").encode("utf-8")
        try:
            self.wfile.write(payload)
            self.wfile.flush()
        except Exception:
            pass


# Global shutdown event
shutdown_event = threading.Event()


def signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM by setting shutdown event."""
    signame = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    log(f"received {signame}, shutting down...")
    shutdown_event.set()


def main():
    # Install signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    os.makedirs(OPS_FILES_BASE_DIR, exist_ok=True)

    log(f"Loading Identity from {IDENTITY_PATH}...")
    
    try:
        # Load Ziti identity
        ziti_id, status_code = openziti.load(IDENTITY_PATH)
    except Exception as e:
        log(f"❌ Failed to load identity: {e}")
        sys.exit(1)

    # Configure ziti bindings for exec and files and ensure files dir exists

    binding_cfg_exec = {"ztx": ziti_id, "service": OPS_EXEC_SERVICE}
    binding_cfg_files = {"ztx": ziti_id, "service": OPS_FILES_SERVICE}
    binding_cfg_forward = {"ztx": ziti_id, "service": OPS_FORWARD_SERVICE}

    log(f"Starting Ziti application with bindings for {OPS_EXEC_SERVICE}, {OPS_FILES_SERVICE} and {OPS_FORWARD_SERVICE}")

    # Use a single 'with' statement for ALL Ziti-enabled operations
    try:
        with openziti.monkeypatch(bindings={
            (BIND_ADDR, OPS_EXEC_BIND_PORT): binding_cfg_exec,
            (BIND_ADDR, OPS_FILES_BIND_PORT): binding_cfg_files,
            (BIND_ADDR, OPS_FORWARD_BIND_PORT): binding_cfg_forward,
        }):
            # Start the exec server
            exec_server = ThreadedTCPServer((BIND_ADDR, OPS_EXEC_BIND_PORT), ExecRequestHandler)
            exec_thread = threading.Thread(target=exec_server.serve_forever, name="ExecServerThread", daemon=True)
            exec_thread.start()
            log(f"ops.exec server listening on {BIND_ADDR}:{OPS_EXEC_BIND_PORT}")

            # Start the files server
            files_server = ThreadedTCPServer((BIND_ADDR, OPS_FILES_BIND_PORT), FilesRequestHandler)
            files_thread = threading.Thread(target=files_server.serve_forever, name="FilesServerThread", daemon=True)
            files_thread.start()
            log(f"ops.files server listening on {BIND_ADDR}:{OPS_FILES_BIND_PORT}")

            # Start the forward server
            forward_server = ThreadedTCPServer((BIND_ADDR, OPS_FORWARD_BIND_PORT), ForwardRequestHandler)
            forward_thread = threading.Thread(target=forward_server.serve_forever, name="ForwardServerThread", daemon=True)
            forward_thread.start()
            log(f"ops.forward server listening on {BIND_ADDR}:{OPS_FORWARD_BIND_PORT}")

            # Wait for shutdown event
            while not shutdown_event.is_set():
                time.sleep(1)

            # Shutdown servers
            log("shutting down servers...")
            exec_server.shutdown()
            files_server.shutdown()
            forward_server.shutdown()
            exec_server.server_close()
            files_server.server_close()
            forward_server.server_close()
            log("servers shut down, exiting.")

    except Exception as e:
        log(f"❌ fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
