"""Local settings page (browser UI) for choosing how many deals to show."""

from __future__ import annotations

import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from .output import brand_header_html, dark_theme_css
from .paths import user_data_dir

VALID_TOP = (10, 20, 30, 40, 50)
DEFAULT_TOP = 30
SETTINGS_PORT = 8765


def top_explicitly_set(argv: list[str] | None = None) -> bool:
    argv = argv if argv is not None else sys.argv[1:]
    for arg in argv:
        if arg in ("-t", "--top"):
            return True
        if arg.startswith("-t") and len(arg) > 2 and arg[2:].isdigit():
            return True
    return False


def _settings_html(selected: int = DEFAULT_TOP) -> str:
    options = []
    for n in VALID_TOP:
        checked = " checked" if n == selected else ""
        options.append(
            f'<label class="choice"><input type="radio" name="top" value="{n}"{checked}>'
            f"<span>{n} deals</span></label>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mizuno Menace</title>
  <style>
{dark_theme_css()}
    .panel {{
      max-width: 420px;
      margin: 0 auto;
      text-align: center;
    }}
    h2 {{
      font-size: 1.1rem;
      font-weight: 600;
      margin: 0 0 1.25rem;
    }}
    .choices {{
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      margin-bottom: 1.5rem;
    }}
    .choice {{
      display: flex;
      align-items: center;
      gap: 0.65rem;
      padding: 0.65rem 0.85rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #252526;
      cursor: pointer;
      text-align: left;
    }}
    .choice:has(input:checked) {{
      border-color: #569cd6;
      background: #2a2d2e;
    }}
    .choice input {{
      accent-color: #569cd6;
    }}
    button {{
      width: 100%;
      padding: 0.75rem 1rem;
      font-size: 1rem;
      font-weight: 600;
      color: #1e1e1e;
      background: #cccccc;
      border: none;
      border-radius: 6px;
      cursor: pointer;
    }}
    button:hover {{
      background: #e8e8e8;
    }}
    .hint {{
      margin-top: 1rem;
      font-size: 0.85rem;
      color: var(--muted);
      line-height: 1.45;
    }}
  </style>
</head>
<body>
  <div class="page panel">
    {brand_header_html()}
    <h2>How many deals to show?</h2>
    <form method="POST" action="/scan">
      <div class="choices">
        {"".join(options)}
      </div>
      <button type="submit">Scan deals</button>
    </form>
    <p class="hint">Scrapes foot-store and eBay (when API keys are in .env) for mens M apparel and mens size 11 shoes, ranked by discount vs MSRP.</p>
  </div>
</body>
</html>
"""


def _waiting_html() -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Scanning…</title>
  <style>{dark_theme_css()}</style>
</head>
<body>
  <div class="page" style="text-align:center;padding-top:3rem;">
    {brand_header_html()}
    <p style="color:#cccccc;">Scanning Mizuno deals… this may take a few minutes.</p>
    <p style="color:#858585;font-size:0.9rem;">Keep this window open — the report will load when finished.</p>
  </div>
</body>
</html>
"""


def prompt_top_count(default: int = DEFAULT_TOP) -> int:
    """Open the settings page and block until the user picks 10–50 deals."""
    if default not in VALID_TOP:
        default = DEFAULT_TOP

    choice: dict[str, int | None] = {"top": None}
    done = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                body = _settings_html(default).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/scan":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8") if length else ""
            params = parse_qs(body)
            try:
                top = int(params.get("top", [default])[0])
            except (TypeError, ValueError):
                top = default
            if top not in VALID_TOP:
                top = default
            choice["top"] = top
            waiting = _waiting_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(waiting)))
            self.end_headers()
            self.wfile.write(waiting)
            done.set()

    server = HTTPServer(("127.0.0.1", SETTINGS_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    webbrowser.open(f"http://127.0.0.1:{SETTINGS_PORT}/")
    done.wait()
    server.shutdown()
    return int(choice["top"] or default)


def save_last_top(top: int) -> None:
    path = user_data_dir() / "settings.json"
    path.write_text(json.dumps({"top": top}), encoding="utf-8")


def load_last_top(default: int = DEFAULT_TOP) -> int:
    path = user_data_dir() / "settings.json"
    if not path.exists():
        return default
    try:
        top = int(json.loads(path.read_text(encoding="utf-8")).get("top", default))
        return top if top in VALID_TOP else default
    except (json.JSONDecodeError, TypeError, ValueError):
        return default
