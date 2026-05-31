"""Local settings page (browser UI) for scan preferences."""

from __future__ import annotations

import html
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from .output import _vertical_brand_aside, brand_header_html, dark_theme_css
from .scan_settings import (
    DEFAULT_TOP,
    ScanSettings,
    VALID_TOP,
)
from .search_criteria import (
    APPAREL_SIZE_OPTIONS,
    SHOE_SIZE_US_OPTIONS,
    scan_description,
)

SETTINGS_PORT = 8765


def top_explicitly_set(argv: list[str] | None = None) -> bool:
    argv = argv if argv is not None else sys.argv[1:]
    for arg in argv:
        if arg in ("-t", "--top"):
            return True
        if arg.startswith("-t") and len(arg) > 2 and arg[2:].isdigit():
            return True
    return False


def _select_options(
    options: tuple[str, ...],
    selected: str,
    *,
    label_fn=None,
) -> str:
    label_fn = label_fn or (lambda v: v)
    parts = []
    for value in options:
        sel = " selected" if value == selected else ""
        parts.append(
            f'<option value="{value}"{sel}>{label_fn(value)}</option>'
        )
    return "".join(parts)


def _settings_html(settings: ScanSettings) -> str:
    settings = settings.normalized()
    top_options = []
    for n in VALID_TOP:
        sel = " selected" if n == settings.top else ""
        top_options.append(f'<option value="{n}"{sel}>Top {n} deals</option>')

    hint = scan_description(
        settings.apparel_size,
        settings.shoe_size_us,
        search_scope=settings.search_scope,
        custom_query=settings.custom_query,
    )
    apparel_options = _select_options(
        APPAREL_SIZE_OPTIONS,
        settings.apparel_size,
        label_fn=lambda s: f"Size {s}",
    )
    shoe_options = _select_options(
        SHOE_SIZE_US_OPTIONS,
        settings.shoe_size_us,
        label_fn=lambda s: f"US {s}",
    )
    custom_body = html.escape(settings.custom_query)

    def scope_checked(value: str) -> str:
        return " checked" if settings.search_scope == value else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mizuno Menace</title>
  <style>
{dark_theme_css()}
    .setup-stage {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: clamp(0.75rem, 2.5vw, 1.75rem);
      margin-top: 0.5rem;
    }}
    .setup-stage .side-brand {{
      flex: 0 0 clamp(72px, 10vw, 120px);
      align-self: stretch;
    }}
    .setup-stage .side-brand img {{
      max-height: min(52vh, 420px);
    }}
    .panel {{
      flex: 0 1 480px;
      max-width: 480px;
      text-align: center;
    }}
    h2 {{
      font-size: 1.15rem;
      font-weight: 600;
      margin: 0 0 0.35rem;
    }}
    h2.deals-heading {{
      text-align: left;
      margin: 0 0 0.45rem;
    }}
    .field {{
      text-align: left;
      margin-bottom: 1rem;
    }}
    .field label {{
      display: block;
      font-size: 0.88rem;
      font-weight: 600;
      margin-bottom: 0.45rem;
      color: var(--fg);
    }}
    select {{
      width: 100%;
      padding: 0.7rem 0.85rem;
      font-size: 1rem;
      color: var(--fg);
      background: #252526;
      border: 1px solid var(--border);
      border-radius: 6px;
      cursor: pointer;
    }}
    select:focus {{
      outline: none;
      border-color: #569cd6;
    }}
    .mode-row {{
      display: flex;
      gap: 0.45rem;
      flex-wrap: wrap;
    }}
    .mode-btn {{
      flex: 1 1 0;
      min-width: 7rem;
      margin: 0;
      cursor: pointer;
    }}
    .mode-btn input {{
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }}
    .mode-btn span {{
      display: block;
      padding: 0.65rem 0.5rem;
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--fg);
      background: #252526;
      border: 1px solid var(--border);
      border-radius: 6px;
      text-align: center;
    }}
    .mode-btn input:checked + span {{
      border-color: #569cd6;
      background: #2a2d2e;
      color: #ffffff;
    }}
    .mode-btn:hover span {{
      border-color: #569cd6;
    }}
    input[type="text"], textarea {{
      width: 100%;
      padding: 0.7rem 0.85rem;
      font-size: 0.95rem;
      color: var(--fg);
      background: #252526;
      border: 1px solid var(--border);
      border-radius: 6px;
      box-sizing: border-box;
      font-family: inherit;
    }}
    input[type="text"]:focus, textarea:focus {{
      outline: none;
      border-color: #569cd6;
    }}
    textarea {{
      min-height: 4.5rem;
      resize: vertical;
    }}
    .field-note {{
      margin: 0.35rem 0 0;
      font-size: 0.8rem;
      color: var(--muted);
      line-height: 1.4;
    }}
    button[type="submit"] {{
      width: 100%;
      padding: 0.75rem 1rem;
      font-size: 1rem;
      font-weight: 600;
      color: #1e1e1e;
      background: #cccccc;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      margin-top: 0.35rem;
    }}
    button[type="submit"]:hover {{
      background: #e8e8e8;
    }}
    .hint {{
      margin-top: 1rem;
      font-size: 0.85rem;
      color: var(--muted);
      line-height: 1.45;
    }}
    @media (max-width: 720px) {{
      .setup-stage .side-brand {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    {brand_header_html()}
    <div class="setup-stage">
      {_vertical_brand_aside()}
      <div class="panel">
        <h2>Configure your scan</h2>
        <form method="POST" action="/scan">
          <div class="field">
            <label>What to search</label>
            <div class="mode-row">
              <label class="mode-btn">
                <input type="radio" name="search_scope" value="both"{scope_checked("both")}>
                <span>Both</span>
              </label>
              <label class="mode-btn">
                <input type="radio" name="search_scope" value="apparel"{scope_checked("apparel")}>
                <span>Apparel only</span>
              </label>
              <label class="mode-btn">
                <input type="radio" name="search_scope" value="shoes"{scope_checked("shoes")}>
                <span>Shoes only</span>
              </label>
            </div>
          </div>
          <div class="field">
            <label for="custom_query">Custom eBay search (optional)</label>
            <textarea id="custom_query" name="custom_query" rows="3"
              placeholder="Example: Mizuno Wave Rider mens size 11 NWT">{custom_body}</textarea>
            <p class="field-note">When you enter text here, the scan uses only this search and ignores the preset queries above. Pick Apparel only or Shoes only to apply the matching size filter.</p>
          </div>
          <div class="field">
            <label for="apparel_size">Apparel size</label>
            <select id="apparel_size" name="apparel_size" aria-label="Apparel size">
              {apparel_options}
            </select>
          </div>
          <div class="field">
            <label for="shoe_size_us">Shoe size (US)</label>
            <select id="shoe_size_us" name="shoe_size_us" aria-label="Shoe size US">
              {shoe_options}
            </select>
          </div>
          <div class="field">
            <h2 class="deals-heading">Choose How Many Deals To Display</h2>
            <select id="top" name="top" aria-label="Number of deals to display">
              {"".join(top_options)}
            </select>
          </div>
          <button type="submit">Start scan</button>
        </form>
        <p class="hint" id="scan-hint">{hint}</p>
      </div>
      {_vertical_brand_aside()}
    </div>
  </div>
  <script>
    function selectedScope() {{
      const picked = document.querySelector('input[name="search_scope"]:checked');
      return picked ? picked.value : 'both';
    }}

    function updateScanHint() {{
      const apparel = document.getElementById('apparel_size').value;
      const shoe = document.getElementById('shoe_size_us').value;
      const scope = selectedScope();
      const custom = document.getElementById('custom_query').value.trim();
      const hint = document.getElementById('scan-hint');
      const prefix = 'Searches eBay for New With Tags, Buy It Now Mizuno listings — ';
      const suffix = ' — then opens a ranked HTML report.';

      if (custom) {{
        hint.textContent = prefix + 'using your custom search "' + custom + '" only' + suffix;
        return;
      }}
      if (scope === 'apparel') {{
        hint.textContent = prefix + 'mens size ' + apparel + ' apparel only' + suffix;
        return;
      }}
      if (scope === 'shoes') {{
        hint.textContent = prefix + 'mens US size ' + shoe + ' shoes only' + suffix;
        return;
      }}
      hint.textContent = prefix + 'mens size ' + apparel + ' apparel and mens US size ' + shoe + ' shoes' + suffix;
    }}

    document.querySelectorAll('input[name="search_scope"]').forEach(function(el) {{
      el.addEventListener('change', updateScanHint);
    }});
    document.getElementById('apparel_size').addEventListener('change', updateScanHint);
    document.getElementById('shoe_size_us').addEventListener('change', updateScanHint);
    document.getElementById('custom_query').addEventListener('input', updateScanHint);
  </script>
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
    <p style="color:#858585;font-size:0.9rem;">Keep this window open — your deal report will open when the scan finishes.</p>
  </div>
</body>
</html>
"""


def prompt_scan_settings(default: ScanSettings | None = None) -> ScanSettings:
    """Open the settings page and block until the user submits scan preferences."""
    default = (default or ScanSettings()).normalized()
    choice: dict[str, ScanSettings | None] = {"settings": None}
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
                top = int(params.get("top", [default.top])[0])
            except (TypeError, ValueError):
                top = default.top
            apparel_size = params.get("apparel_size", [default.apparel_size])[0]
            shoe_size_us = params.get("shoe_size_us", [default.shoe_size_us])[0]
            search_scope = params.get("search_scope", [default.search_scope])[0]
            custom_query = params.get("custom_query", [default.custom_query])[0]
            settings = ScanSettings(
                top=top,
                apparel_size=apparel_size,
                shoe_size_us=shoe_size_us,
                search_scope=search_scope,
                custom_query=custom_query,
            ).normalized()
            choice["settings"] = settings
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
    return choice["settings"] or default


def prompt_top_count(default: int = DEFAULT_TOP) -> int:
    """Legacy helper — returns only deal count from the settings page."""
    settings = prompt_scan_settings(ScanSettings(top=default))
    return settings.top
