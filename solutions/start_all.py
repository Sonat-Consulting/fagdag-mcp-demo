#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# ///
"""Start all three MCP solution servers at once.

Usage (from anywhere in the repo):

    uv run solutions/start_all.py

Launches postal_codes (8036), OAuth (8037) and consultant_map (8038) each in
their own `uv run python server.py` subprocess, using their own project's
virtualenv. Output from each server is prefixed with its name. Ctrl+C stops
all three.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

SOLUTIONS_DIR = Path(__file__).resolve().parent

SERVERS = [
    ("postal_codes", "http://localhost:8036/mcp"),
    ("OAuth", "http://localhost:8037/mcp"),
    ("consultant_map", "http://localhost:8038/mcp"),
]


def stream_output(name: str, process: subprocess.Popen) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{name}] {line}", end="")


def main() -> None:
    processes: list[subprocess.Popen] = []
    threads: list[threading.Thread] = []

    for name, url in SERVERS:
        project_dir = SOLUTIONS_DIR / name
        print(f"Starting {name} ({url}) in {project_dir} ...")
        process = subprocess.Popen(
            ["uv", "run", "python", "server.py"],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        processes.append(process)
        thread = threading.Thread(target=stream_output, args=(name, process), daemon=True)
        thread.start()
        threads.append(thread)

    print("\nAll servers starting. Press Ctrl+C to stop them.\n")

    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        print("\nStopping all servers ...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    sys.exit(main())
