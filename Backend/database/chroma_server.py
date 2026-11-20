"""
Local Chroma HTTP server lifecycle for one-command Backend startup.

`ensure_chroma_server()` starts `chroma run` against CHROMA_PERSIST_DIR when
nothing is listening on CHROMA_HOST:CHROMA_PORT. Idempotent; cleans up the
child process on exit when we started it.
"""
from __future__ import annotations

import atexit
import os
import shutil
import socket
import subprocess
import sys
import time
from typing import Optional

from dotenv import load_dotenv

_proc: Optional[subprocess.Popen] = None
_started_by_us = False
_atexit_registered = False

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
READY_TIMEOUT_S = 45.0
READY_POLL_S = 0.4


def chroma_host() -> str:
    load_dotenv()
    return (os.environ.get("CHROMA_HOST") or DEFAULT_HOST).strip() or DEFAULT_HOST


def chroma_port() -> int:
    load_dotenv()
    raw = (os.environ.get("CHROMA_PORT") or str(DEFAULT_PORT)).strip()
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT


def chroma_persist_dir() -> str:
    load_dotenv()
    configured = (os.environ.get("CHROMA_PERSIST_DIR") or "").strip()
    if configured:
        return configured
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(backend_root, "vector_store")


def chroma_mode() -> str:
    """http (default) | persistent."""
    load_dotenv()
    mode = (os.environ.get("CHROMA_MODE") or "http").strip().lower()
    if mode in ("persistent", "persist", "local"):
        return "persistent"
    return "http"


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.75):
            return True
    except OSError:
        return False


def _chroma_cli() -> str:
    found = shutil.which("chroma")
    if found:
        return found
    raise RuntimeError(
        "chroma CLI not found on PATH. Install chromadb "
        "(pip install chromadb) so `chroma run` is available."
    )


def _stop_server() -> None:
    global _proc, _started_by_us
    if not _started_by_us or _proc is None:
        return
    proc = _proc
    _proc = None
    _started_by_us = False
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
        print("LOG: Chroma HTTP server stopped", flush=True)
    except Exception as exc:
        print(
            f"LOG: Chroma HTTP server stop failed ({type(exc).__name__}: {exc})",
            flush=True,
        )


def _register_atexit() -> None:
    global _atexit_registered
    if _atexit_registered:
        return
    atexit.register(_stop_server)
    _atexit_registered = True


def ensure_chroma_server(
    *,
    host: str | None = None,
    port: int | None = None,
    persist_dir: str | None = None,
    timeout_s: float = READY_TIMEOUT_S,
) -> dict:
    """
    Ensure a Chroma HTTP server is reachable.

    If the port is already open, reuse it (do not spawn). Otherwise spawn
    `chroma run --path … --host … --port …` and wait until ready.

    Returns dict with host, port, path, started (bool), reused (bool).
    No-op when CHROMA_MODE=persistent (PersistentClient needs no server).
    """
    global _proc, _started_by_us

    if chroma_mode() == "persistent":
        return {
            "mode": "persistent",
            "started": False,
            "reused": False,
            "skipped": True,
        }

    host = (host or chroma_host()).strip() or DEFAULT_HOST
    port = int(port or chroma_port())
    path = persist_dir or chroma_persist_dir()
    os.makedirs(path, exist_ok=True)

    if _port_open(host, port):
        print(
            f"LOG: Chroma HTTP already listening on {host}:{port} "
            f"(persist={path})",
            flush=True,
        )
        return {
            "mode": "http",
            "host": host,
            "port": port,
            "path": path,
            "started": False,
            "reused": True,
            "skipped": False,
        }

    if _proc is not None and _proc.poll() is None:
        # We already spawned; wait for ready below.
        pass
    else:
        cli = _chroma_cli()
        cmd = [
            cli,
            "run",
            "--path",
            path,
            "--host",
            host,
            "--port",
            str(port),
        ]
        popen_kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if sys.platform == "win32":
            # Avoid an extra console window when Flask starts Chroma.
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if creationflags:
                popen_kwargs["creationflags"] = creationflags

        print(
            f"LOG: Starting Chroma HTTP server on {host}:{port} "
            f"(persist={path})",
            flush=True,
        )
        _proc = subprocess.Popen(cmd, **popen_kwargs)
        _started_by_us = True
        _register_atexit()

    deadline = time.time() + max(5.0, float(timeout_s))
    while time.time() < deadline:
        if _proc is not None and _proc.poll() is not None:
            raise RuntimeError(
                f"Chroma server exited early with code {_proc.returncode}. "
                f"Command: chroma run --path {path} --host {host} --port {port}"
            )
        if _port_open(host, port):
            print(
                f"LOG: Chroma HTTP server ready on {host}:{port}",
                flush=True,
            )
            return {
                "mode": "http",
                "host": host,
                "port": port,
                "path": path,
                "started": _started_by_us,
                "reused": False,
                "skipped": False,
            }
        time.sleep(READY_POLL_S)

    _stop_server()
    raise TimeoutError(
        f"Chroma HTTP server did not become ready on {host}:{port} "
        f"within {timeout_s:.0f}s"
    )


def should_manage_chroma_at_flask_startup(*, debug: bool) -> bool:
    """
    Avoid double-start under Flask's debug reloader.

    - debug=False: manage in this process
    - debug=True: manage only in the reloader child (WERKZEUG_RUN_MAIN=true)
    """
    if not debug:
        return True
    return os.environ.get("WERKZEUG_RUN_MAIN") == "true"
