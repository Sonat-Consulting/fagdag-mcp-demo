#!/usr/bin/env python3
"""Serve the presentation decks in this folder over HTTP.

Usage:
    python3 presentations/serve.py            # http://127.0.0.1:8888
    python3 presentations/serve.py --port 9000
    python3 presentations/serve.py --host 0.0.0.0   # reachable from the room

The root URL lists every .html file in this folder, so a new deck shows up
without touching this script.
"""

from __future__ import annotations

import argparse
import html
import re
import socket
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PRESENTATIONS_DIR = Path(__file__).resolve().parent
# The repo README sits outside the served folder, so it gets its own routes below.
REPO_README = PRESENTATIONS_DIR.parent / "README.md"
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)

# Decks are listed in session order; anything not named here follows alphabetically.
DECK_ORDER = ("mcp_fastmcp.html", "mcp_exercises.html")


def deck_title(path: Path) -> str:
    """Pull the <title> out of a deck, falling back to the file name."""
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return path.stem
    match = TITLE_RE.search(head)
    if not match:
        return path.stem
    return html.unescape(" ".join(match.group(1).split())) or path.stem


def find_decks() -> list[tuple[str, str]]:
    """Return (filename, title) for every deck, in DECK_ORDER then alphabetically."""

    def sort_key(path: Path) -> tuple[int, str]:
        try:
            return (DECK_ORDER.index(path.name), "")
        except ValueError:
            return (len(DECK_ORDER), path.name)

    paths = (p for p in PRESENTATIONS_DIR.glob("*.html") if p.name != "index.html")
    return [(p.name, deck_title(p)) for p in sorted(paths, key=sort_key)]


def render_index() -> bytes:
    decks = find_decks()
    if decks:
        cards = "\n".join(
            f"""      <a class="card" href="{html.escape(name)}">
        <span class="title">{html.escape(title)}</span>
        <span class="file">{html.escape(name)}</span>
      </a>"""
            for name, title in decks
        )
    else:
        cards = '      <p class="empty">No .html decks found in this folder.</p>'

    if REPO_README.is_file():
        cards += """
      <a class="card doc" href="readme">
        <span class="title">Repo README</span>
        <span class="file">README.md &mdash; setup, database, MCP server</span>
      </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Fagdag MCP &mdash; Presentations</title>
  <style>
    :root {{
      --bg: #002b36;
      --fg: #eee8d5;
      --accent: #e8a838;
      --accent2: #4fc3f7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      background: var(--bg);
      color: var(--fg);
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
    }}
    main {{ width: 100%; max-width: 720px; }}
    h1 {{
      margin: 0 0 0.25em;
      font-size: 2.2rem;
      color: var(--accent);
      font-weight: 600;
    }}
    p.lead {{ margin: 0 0 2rem; opacity: 0.75; }}
    .cards {{ display: grid; gap: 1rem; }}
    .card {{
      display: flex;
      flex-direction: column;
      gap: 0.35rem;
      padding: 1.1rem 1.3rem;
      border: 1px solid rgba(238, 232, 213, 0.18);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.05);
      text-decoration: none;
      color: inherit;
      transition: border-color 0.15s, transform 0.15s, background 0.15s;
    }}
    .card:hover {{
      border-color: var(--accent);
      background: rgba(255, 255, 255, 0.09);
      transform: translateY(-2px);
    }}
    .card .title {{ font-size: 1.25rem; color: var(--accent2); }}
    .card.doc .title {{ color: var(--accent); }}
    .card .file {{ font-size: 0.85rem; opacity: 0.6; font-family: ui-monospace, Menlo, monospace; }}
    .empty {{ opacity: 0.7; }}
  </style>
</head>
<body>
  <main>
    <h1>Fagdag MCP</h1>
    <p class="lead">Slides for the session. Arrow keys to navigate, <kbd>Esc</kbd> for the overview.</p>
    <div class="cards">
{cards}
    </div>
  </main>
</body>
</html>
""".encode("utf-8")


README_PAGE = b"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Repo README &mdash; Fagdag MCP</title>
  <style>
    :root {
      --bg: #002b36;
      --fg: #eee8d5;
      --accent: #e8a838;
      --accent2: #4fc3f7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 2.5rem 2rem 6rem;
      background: var(--bg);
      color: var(--fg);
      font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      line-height: 1.65;
    }
    main { max-width: 880px; margin: 0 auto; }
    a { color: var(--accent2); }
    a.back {
      display: inline-block;
      margin-bottom: 2rem;
      text-decoration: none;
      opacity: 0.75;
    }
    a.back:hover { opacity: 1; }
    h1, h2, h3, h4 { color: var(--accent); line-height: 1.25; margin: 2rem 0 0.6rem; }
    h1 { font-size: 2rem; margin-top: 0; }
    h2 { font-size: 1.5rem; border-bottom: 1px solid rgba(238, 232, 213, 0.15); padding-bottom: 0.3rem; }
    h3 { font-size: 1.2rem; color: var(--accent2); }
    code {
      font-family: ui-monospace, Menlo, monospace;
      font-size: 0.9em;
      background: rgba(255, 255, 255, 0.09);
      padding: 0.1em 0.35em;
      border-radius: 4px;
    }
    pre {
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(238, 232, 213, 0.12);
      border-radius: 6px;
      padding: 1rem;
      overflow-x: auto;
    }
    pre code { background: none; padding: 0; }
    blockquote {
      margin: 1rem 0;
      padding: 0.4em 1em;
      border-left: 4px solid var(--accent);
      background: rgba(255, 255, 255, 0.06);
    }
    table { border-collapse: collapse; margin: 1rem 0; }
    th, td { border: 1px solid rgba(238, 232, 213, 0.18); padding: 0.4em 0.8em; text-align: left; }
    hr { border: none; border-top: 1px solid rgba(238, 232, 213, 0.15); margin: 2rem 0; }
    #error { color: #e57373; }
  </style>
</head>
<body>
  <main>
    <a class="back" href="/">&larr; All presentations</a>
    <div id="content">Loading README&hellip;</div>
  </main>
  <script type="module">
    import { marked } from "https://cdn.jsdelivr.net/npm/marked@12.0.2/lib/marked.esm.js";
    const target = document.getElementById("content");
    try {
      const res = await fetch("/README.md", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      target.innerHTML = marked.parse(await res.text(), { gfm: true });
    } catch (err) {
      target.innerHTML = `<p id="error">Could not render README: ${err.message}. ` +
        `<a href="/README.md">Open the raw file</a>.</p>`;
    }
  </script>
</body>
</html>
"""


class PresentationHandler(SimpleHTTPRequestHandler):
    """Static file server that generates the index and README pages on the fly."""

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self.send_body(render_index(), "text/html; charset=utf-8")
            return
        if path in ("/readme", "/readme/"):
            self.send_body(README_PAGE, "text/html; charset=utf-8")
            return
        if path == "/README.md":
            try:
                self.send_body(REPO_README.read_bytes(), "text/markdown; charset=utf-8")
            except OSError:
                self.send_error(404, "README.md not found")
            return
        super().do_GET()

    def send_body(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        # Decks are edited live during the session; never serve a stale copy.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} - {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8888, help="port (default: 8888)")
    parser.add_argument("--open", action="store_true", help="open the index in a browser")
    args = parser.parse_args()

    handler = partial(PresentationHandler, directory=str(PRESENTATIONS_DIR))
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        raise SystemExit(
            f"Could not bind {args.host}:{args.port} ({exc}). Try --port with another value."
        )

    url = f"http://{'127.0.0.1' if args.host in ('0.0.0.0', '') else args.host}:{args.port}/"
    print(f"Serving {PRESENTATIONS_DIR} at {url}")
    for name, title in find_decks():
        print(f"  {url}{name}  ->  {title}")
    if REPO_README.is_file():
        print(f"  {url}readme  ->  Repo README")
    if args.host in ("0.0.0.0", ""):
        try:
            print(f"On this network: http://{socket.gethostbyname(socket.gethostname())}:{args.port}/")
        except OSError:
            pass
    print("Ctrl+C to stop.")

    if args.open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
