#!/usr/bin/env python3
import json
import os
import signal
import socketserver
import subprocess
import sys
import threading
import time
import atexit
from typing import List

# Third-party
import openziti # type: ignore

# Configuration
IDENTITY_PATH = os.environ.get("ZITI_EDGE_IDENTITY", "/ziti-config/edge-device.json")
SERVICE_NAME = os.environ.get("OPS_EXEC_SERVICE", "ops.exec")
BIND_ADDR = os.environ.get("OPS_EXEC_BIND_ADDR", "0.0.0.0")
BIND_PORT = int(os.environ.get("OPS_EXEC_BIND_PORT", "5555"))
TIMEOUT_SECS = int(os.environ.get("OPS_EXEC_TIMEOUT_SECONDS", "30"))

# Simple, safe default allowlist. Override with OPS_EXEC_ALLOWLIST="ls,uname,uptime,whoami,echo"
DEFAULT_ALLOWLIST = ["ls", "uname", "whoami", "echo"]
ALLOWLIST: List[str] = [c.strip() for c in os.environ.get("OPS_EXEC_ALLOWLIST", ",".join(DEFAULT_ALLOWLIST)).split(",") if c.strip()]

MAX_OUTPUT_CHARS = int(os.environ.get("OPS_EXEC_MAX_OUTPUT", "100000"))  # 100KB


def log(msg: str):
    print(f"[edge-agent][ops.exec] {msg}")


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
    
    # Configure ziti binding: redirect OS listen on BIND_ADDR:BIND_PORT to Ziti service SERVICE_NAME
    binding_cfg = {"ztx": IDENTITY_PATH, "service": SERVICE_NAME}
    patcher = None
    try:
        # Keep a handle to the patcher if available so we can explicitly unpatch on shutdown
        patcher = openziti.monkeypatch(bindings={(BIND_ADDR, BIND_PORT): binding_cfg})
    except Exception:
        # Some SDK versions don't return a patcher; proceed regardless
        openziti.monkeypatch(bindings={(BIND_ADDR, BIND_PORT): binding_cfg})

    # Best-effort cleanup at process exit as a safety net
    def _cleanup_on_exit():
        try:
            log("cleaning up ziti bindings...")
            if patcher and hasattr(patcher, "close"):
                patcher.close()
        except Exception:
            pass
        try:
            # If the SDK exposes an unmonkeypatch/reset, call it; ignore if not present
            if hasattr(openziti, "unmonkeypatch"):
                openziti.unmonkeypatch()
        except Exception:
            pass

    atexit.register(_cleanup_on_exit)

    with ThreadedTCPServer((BIND_ADDR, BIND_PORT), ExecRequestHandler) as srv:
        log(
            f"binding service '{SERVICE_NAME}' with identity '{IDENTITY_PATH}' as {BIND_ADDR}:{BIND_PORT}"
        )
        
        # Run server in a thread so we can check shutdown_event
        server_thread = threading.Thread(target=srv.serve_forever, daemon=True)
        server_thread.start()
        
        # Poll shutdown event to allow signal handlers to work
        while not shutdown_event.is_set():
            time.sleep(0.2)
        
        # Clean shutdown
        log("stopping server...")
        srv.shutdown()
        # Ensure the underlying listening socket is closed
        try:
            srv.server_close()
        except Exception:
            pass
        server_thread.join(timeout=2)
        
        # Explicitly unpatch/cleanup Ziti bindings to drop the terminator
        try:
            if patcher and hasattr(patcher, "close"):
                patcher.close()
        except Exception:
            pass
        try:
            if hasattr(openziti, "unmonkeypatch"):
                openziti.unmonkeypatch()
        except Exception:
            pass

        log("exited cleanly")
        sys.exit(0)


if __name__ == "__main__":
    main()
