from __future__ import annotations

import argparse
import configparser
import json
import logging
import re
import subprocess
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .config import atomic_write_config, config_from_mapping, config_to_toml, load_config


LOGGER = logging.getLogger(__name__)
ROUTER_SERVICE = "ysf-bm-router.service"
DEFAULT_WPSD_CSS_PATH = "/etc/wpsd-css.ini"
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

FALLBACK_THEME = {
    "source": "fallback",
    "path": "",
    "variables": {
        "--bg": "#050708",
        "--panel": "#0b1012",
        "--panel-2": "#11191c",
        "--line": "#253338",
        "--text": "#edf6f4",
        "--muted": "#98aaa8",
        "--accent": "#00c16a",
        "--accent-2": "#f5a524",
        "--danger": "#ff5c66",
        "--field": "#06090a",
        "--banner": "#020405",
        "--link": "#b58cff",
        "--row-even": "#080e12",
        "--row-odd": "#04080a",
    },
}


def build_config_from_payload(payload: dict[str, Any]):
    config = config_from_mapping(
        {
            "ysf": _mapping(payload.get("ysf")),
            "brandmeister": _mapping(payload.get("brandmeister")),
            "behavior": _mapping(payload.get("behavior")),
            "routes": [_mapping(route) for route in payload.get("routes", [])],
        }
    )
    config.validate()
    return config


def _mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return value


def run_admin_server(
    config_path: str | Path,
    host: str = "0.0.0.0",
    port: int = 8092,
    wpsd_css_path: str | Path = DEFAULT_WPSD_CSS_PATH,
) -> None:
    resolved_config = Path(config_path)
    resolved_wpsd_css = Path(wpsd_css_path)
    handler = _make_handler(resolved_config, resolved_wpsd_css)
    server = ThreadingHTTPServer((host, port), handler)
    LOGGER.info("admin listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _make_handler(config_path: Path, wpsd_css_path: Path):
    class AdminHandler(BaseHTTPRequestHandler):
        server_version = "YSFBMRouterAdmin/0.1"

        def do_GET(self) -> None:
            if self.path in {"/", "/index.html"}:
                self._send_text(INDEX_HTML, "text/html; charset=utf-8")
                return
            if self.path == "/api/config":
                self._send_json(_read_config_response(config_path))
                return
            if self.path == "/api/status":
                self._send_json(_status_response(config_path, wpsd_css_path))
                return
            if self.path == "/api/theme":
                self._send_json({"ok": True, "theme": read_wpsd_theme(wpsd_css_path)})
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path == "/api/config":
                self._save_config(config_path)
                return
            if self.path == "/api/restart":
                restart = _restart_router()
                self._send_json(
                    {
                        "ok": restart["ok"],
                        "status": _status_response(config_path, wpsd_css_path),
                        "restart": restart,
                    }
                )
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            LOGGER.info("%s - %s", self.address_string(), format % args)

        def _save_config(self, config_path: Path) -> None:
            try:
                payload = self._read_json()
                config = build_config_from_payload(payload)
                atomic_write_config(config_path, config_to_toml(config))
                restart = None
                if bool(payload.get("restart")):
                    restart = _restart_router()
                self._send_json(
                    {
                        "ok": restart is None or restart["ok"],
                        "message": "Configuration saved.",
                        "status": _status_response(config_path, wpsd_css_path),
                        "restart": restart,
                    }
                )
            except Exception as exc:
                LOGGER.exception("admin config save failed")
                self._send_json(
                    {
                        "ok": False,
                        "message": str(exc),
                        "status": _status_response(config_path, wpsd_css_path),
                    },
                    HTTPStatus.BAD_REQUEST,
                )

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("content-length", "0"))
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, text: str, content_type: str) -> None:
            body = text.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", content_type)
            self.send_header("cache-control", "no-store")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return AdminHandler


def _read_config_response(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    return {"ok": True, "config": asdict(config), "status": _status_response(config_path)}


def _status_response(config_path: Path, wpsd_css_path: Path | None = None) -> dict[str, Any]:
    exists = config_path.exists()
    status = {
        "config_path": str(config_path),
        "config_exists": exists,
        "config_mtime": config_path.stat().st_mtime if exists else None,
        "backup_path": str(config_path.with_suffix(config_path.suffix + ".bak")),
        "router_service": _systemctl("is-active", ROUTER_SERVICE),
        "admin_service": _systemctl("is-active", "ysf-bm-router-admin.service"),
    }
    if wpsd_css_path is not None:
        status["theme"] = read_wpsd_theme(wpsd_css_path)
    return status


def read_wpsd_theme(path: str | Path = DEFAULT_WPSD_CSS_PATH) -> dict[str, Any]:
    theme_path = Path(path)
    if not theme_path.exists():
        return _fallback_theme()

    parser = configparser.ConfigParser()
    parser.optionxform = str
    try:
        parser.read(theme_path, encoding="utf-8")
        variables = dict(FALLBACK_THEME["variables"])
        background = parser["Background"] if parser.has_section("Background") else {}
        text = parser["Text"] if parser.has_section("Text") else {}
        extras = parser["ExtraSettings"] if parser.has_section("ExtraSettings") else {}
        _set_color(variables, "--bg", background.get("PageColor"))
        _set_color(variables, "--panel", background.get("ContentColor"))
        _set_color(variables, "--panel-2", background.get("NavPanelColor"))
        _set_color(variables, "--line", extras.get("TableBorderColor"))
        _set_color(variables, "--text", text.get("TextColor"))
        _set_color(variables, "--muted", text.get("TextSectionColor"))
        _set_color(variables, "--accent", background.get("ModeCellActiveColor"))
        _set_color(variables, "--accent-2", text.get("BannersColor"))
        _set_color(variables, "--danger", background.get("ModeCellInactiveColor"))
        _set_color(variables, "--field", background.get("DropdownColor"))
        _set_color(variables, "--banner", background.get("BannersColor"))
        _set_color(variables, "--link", text.get("TextLinkColor"))
        _set_color(variables, "--row-even", background.get("TableRowBgEvenColor"))
        _set_color(variables, "--row-odd", background.get("TableRowBgOddColor"))
        return {
            "source": "wpsd",
            "path": str(theme_path),
            "variables": variables,
        }
    except Exception as exc:
        LOGGER.warning("failed to read WPSD theme from %s: %s", theme_path, exc)
        theme = _fallback_theme()
        theme["error"] = str(exc)
        return theme


def _fallback_theme() -> dict[str, Any]:
    return {
        "source": FALLBACK_THEME["source"],
        "path": FALLBACK_THEME["path"],
        "variables": dict(FALLBACK_THEME["variables"]),
    }


def _set_color(variables: dict[str, str], css_variable: str, value: str | None) -> None:
    if value and HEX_COLOR_RE.match(value):
        variables[css_variable] = value.lower()


def _restart_router() -> dict[str, Any]:
    result = _run_systemctl("restart", ROUTER_SERVICE)
    active = _systemctl("is-active", ROUTER_SERVICE)
    return {
        "ok": result.returncode == 0,
        "command": f"systemctl restart {ROUTER_SERVICE}",
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "router_service": active,
    }


def _systemctl(*args: str) -> str:
    result = _run_systemctl(*args)
    text = result.stdout.strip() or result.stderr.strip()
    return text or f"systemctl exited {result.returncode}"


def _run_systemctl(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["systemctl", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:  # pragma: no cover - platform dependent
        return subprocess.CompletedProcess(["systemctl", *args], 1, "", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser(prog="ysf-bm-router-admin")
    parser.add_argument(
        "--config",
        default="/opt/ysf-bm-router/config/ysf-bm-router.toml",
        help="Path to ysf-bm-router TOML configuration.",
    )
    parser.add_argument(
        "--wpsd-css",
        default=DEFAULT_WPSD_CSS_PATH,
        help="Path to WPSD dashboard CSS/theme INI.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Admin UI bind address.")
    parser.add_argument("--port", default=8092, type=int, help="Admin UI TCP port.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_admin_server(args.config, args.host, args.port, args.wpsd_css)
    return 0


INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>YSF-BM Router Admin</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #050708;
      --panel: #0b1012;
      --panel-2: #11191c;
      --line: #253338;
      --text: #edf6f4;
      --muted: #98aaa8;
      --accent: #00c16a;
      --accent-2: #f5a524;
      --danger: #ff5c66;
      --field: #06090a;
      --banner: #020405;
      --link: #b58cff;
      --row-even: #080e12;
      --row-odd: #04080a;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
    }
    header {
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 1rem clamp(1rem, 4vw, 2rem);
      border-bottom: 1px solid var(--line);
      background: var(--banner);
      backdrop-filter: blur(12px);
    }
    h1 { margin: 0; font-size: 1.05rem; letter-spacing: 0; }
    main {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 22rem;
      gap: 1rem;
      padding: 1rem clamp(1rem, 4vw, 2rem) 2rem;
    }
    section, aside {
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      overflow: hidden;
    }
    h2 {
      margin: 0;
      padding: 0.8rem 1rem;
      border-bottom: 1px solid var(--line);
      color: var(--accent-2);
      font-size: 0.9rem;
    }
    .stack { display: grid; gap: 1rem; }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 0.75rem;
      padding: 1rem;
    }
    label { display: grid; gap: 0.35rem; color: var(--muted); font-size: 0.75rem; }
    input, select {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--field);
      color: var(--text);
      padding: 0.55rem 0.6rem;
      font: inherit;
    }
    input[type="checkbox"] { width: 1rem; height: 1rem; }
    .check {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 2.4rem;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 0.45rem 0.6rem;
      background: var(--field);
    }
    button {
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--text);
      padding: 0.55rem 0.8rem;
      font-weight: 700;
      cursor: pointer;
    }
    button.primary { border-color: #088a50; background: #047846; }
    button.warn { border-color: #8f6417; background: #5d410e; }
    button.danger { border-color: #8e2630; background: #621a22; }
    .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; }
    .route-tools {
      display: flex;
      justify-content: space-between;
      gap: 0.75rem;
      align-items: center;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--line);
    }
    .routes { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 58rem; }
    th, td { border-bottom: 1px solid var(--line); padding: 0.45rem; text-align: left; }
    th { color: var(--accent-2); background: var(--banner); font-size: 0.72rem; }
    tbody tr:nth-child(even) { background: var(--row-even); }
    tbody tr:nth-child(odd) { background: var(--row-odd); }
    td input { padding: 0.45rem; }
    .status {
      padding: 1rem;
      display: grid;
      gap: 0.7rem;
      color: var(--muted);
      font-size: 0.83rem;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      width: fit-content;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 0.28rem 0.55rem;
      color: var(--text);
      background: var(--field);
    }
    .pill strong { overflow-wrap: anywhere; }
    .dot { width: 0.55rem; height: 0.55rem; border-radius: 50%; background: var(--danger); }
    .dot.active { background: var(--accent); }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      padding: 1rem;
      min-height: 8rem;
      border-top: 1px solid var(--line);
      background: var(--field);
      color: var(--text);
      font-size: 0.8rem;
    }
    .muted { color: var(--muted); }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>YSF-BM Router Admin</h1>
      <div class="muted">Fusion Hotspot Users - Channelize DMR Talkgroups</div>
    </div>
    <div class="actions">
      <button onclick="loadConfig()">Reload</button>
      <button class="warn" onclick="restartRouter()">Restart Router</button>
      <button class="primary" onclick="saveConfig(true)">Apply & Restart</button>
    </div>
  </header>
  <main>
    <div class="stack">
      <section>
        <h2>YSF Listener</h2>
        <div class="grid" id="ysf"></div>
      </section>
      <section>
        <h2>BrandMeister</h2>
        <div class="grid" id="brandmeister"></div>
      </section>
      <section>
        <h2>Behavior</h2>
        <div class="grid" id="behavior"></div>
      </section>
      <section>
        <h2>DG-ID Routes</h2>
        <div class="route-tools">
          <span class="muted">Map up to 99 Yaesu DG-IDs to BrandMeister talkgroups.</span>
          <button onclick="addRoute()">Add Route</button>
        </div>
        <div class="routes">
          <table>
            <thead>
              <tr>
                <th>Enabled</th><th>DG-ID</th><th>Talkgroup</th><th>Short Name</th>
                <th>Long Name</th><th>Region</th><th>Sort</th><th></th>
              </tr>
            </thead>
            <tbody id="routes"></tbody>
          </table>
        </div>
      </section>
    </div>
    <aside>
      <h2>Status</h2>
      <div class="status">
        <span class="pill"><span id="routerDot" class="dot"></span> Router: <strong id="routerState">unknown</strong></span>
        <span>Config: <strong id="configPath"></strong></span>
        <span>Backup: <strong id="backupPath"></strong></span>
        <span>Theme: <strong id="themeState">fallback</strong></span>
        <div class="actions">
          <button onclick="saveConfig(false)">Save Only</button>
          <button class="primary" onclick="saveConfig(true)">Apply & Restart</button>
        </div>
      </div>
      <pre id="log">Loading...</pre>
    </aside>
  </main>
  <script>
    const fields = {
      ysf: [
        ["listen_address", "Listen Address", "text"],
        ["listen_port", "Listen Port", "number"],
        ["reflector_name", "Reflector Name", "text"]
      ],
      brandmeister: [
        ["server", "YSF Direct Server", "text"],
        ["port", "YSF Direct Port", "number"],
        ["callsign", "Callsign", "text"],
        ["dmr_id", "DMR ID / Hotspot ID", "text"],
        ["password", "Hotspot Password", "password"],
        ["backend", "Backend", "select", ["ysf_direct", "dmr_master", "hybrid_dmr_return"]],
        ["master_server", "DMR Master Server", "text"],
        ["master_port", "DMR Master Port", "number"],
        ["master_password", "DMR Master Password", "password"],
        ["master_local_port", "DMR Local Port", "number"],
        ["master_jitter_ms", "DMR Jitter ms", "number"],
        ["master_options", "DMR Options", "text"],
        ["hotspot_type", "Hotspot Type", "text"],
        ["rx_frequency", "RX Frequency", "number"],
        ["tx_frequency", "TX Frequency", "number"],
        ["color_code", "Color Code", "number"],
        ["power", "Power", "number"],
        ["latitude", "Latitude", "number"],
        ["longitude", "Longitude", "number"],
        ["height", "Height", "number"],
        ["location", "Location", "text"],
        ["description", "Description", "text"],
        ["url", "URL", "text"],
        ["version", "Version", "text"]
      ],
      behavior: [
        ["default_dgid", "Default DG-ID", "number"],
        ["return_to_default_minutes", "Return To Default Minutes", "number"],
        ["tg_change_silence_seconds", "TG Change Silence Seconds", "number"],
        ["return_frame_interval_seconds", "Return Frame Interval Seconds", "number"],
        ["return_start_delay_seconds", "Return Start Delay Seconds", "number"],
        ["rewrite_return_dgid", "Rewrite Return DG-ID", "checkbox"],
        ["rewrite_return_source", "Rewrite Return Source", "checkbox"],
        ["insert_return_header", "Insert Return Header", "checkbox"],
        ["suppress_route_change_transmission", "Suppress Route Change TX", "checkbox"],
        ["show_dgid_callsign", "Show DG-ID Callsign", "checkbox"],
        ["acknowledge_tg_change", "Acknowledge TG Change", "checkbox"]
      ]
    };
    let config = null;

    function inputId(section, key) { return `${section}_${key}`; }
    function log(message) { document.getElementById("log").textContent = message; }

    async function loadTheme() {
      try {
        const response = await fetch("/api/theme");
        const data = await response.json();
        if (!data.ok || !data.theme) return;
        applyTheme(data.theme);
      } catch (error) {
        console.warn("Theme load failed", error);
      }
    }

    function applyTheme(theme) {
      const variables = theme.variables || {};
      Object.entries(variables).forEach(([key, value]) => {
        if (key.startsWith("--") && /^#[0-9a-fA-F]{6}$/.test(value)) {
          document.documentElement.style.setProperty(key, value);
        }
      });
      const label = theme.source === "wpsd" ? `WPSD (${theme.path})` : "fallback";
      document.getElementById("themeState").textContent = label;
    }

    function renderSection(section) {
      const node = document.getElementById(section);
      node.innerHTML = "";
      fields[section].forEach(([key, label, type, options]) => {
        const wrapper = document.createElement("label");
        wrapper.textContent = label;
        if (type === "checkbox") {
          wrapper.className = "check";
          const input = document.createElement("input");
          input.type = "checkbox";
          input.id = inputId(section, key);
          input.checked = Boolean(config[section][key]);
          wrapper.appendChild(input);
        } else if (type === "select") {
          const select = document.createElement("select");
          select.id = inputId(section, key);
          options.forEach((value) => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
          });
          select.value = config[section][key] ?? "";
          wrapper.appendChild(select);
        } else {
          const input = document.createElement("input");
          input.type = type;
          input.id = inputId(section, key);
          input.step = type === "number" ? "any" : "";
          input.value = config[section][key] ?? "";
          wrapper.appendChild(input);
        }
        node.appendChild(wrapper);
      });
    }

    function renderRoutes() {
      const body = document.getElementById("routes");
      body.innerHTML = "";
      config.routes.forEach((route, index) => {
        const row = document.createElement("tr");
        [
          ["enabled", "checkbox"],
          ["dgid", "number"],
          ["talkgroup", "number"],
          ["short_name", "text"],
          ["long_name", "text"],
          ["region", "text"],
          ["sort_order", "number"]
        ].forEach(([key, type]) => {
          const cell = document.createElement("td");
          const input = document.createElement("input");
          input.type = type;
          input.dataset.routeIndex = index;
          input.dataset.routeKey = key;
          if (type === "checkbox") input.checked = Boolean(route[key]);
          else input.value = route[key] ?? "";
          cell.appendChild(input);
          row.appendChild(cell);
        });
        const actions = document.createElement("td");
        const remove = document.createElement("button");
        remove.className = "danger";
        remove.textContent = "Remove";
        remove.onclick = () => { config.routes.splice(index, 1); renderRoutes(); };
        actions.appendChild(remove);
        row.appendChild(actions);
        body.appendChild(row);
      });
    }

    function renderStatus(status) {
      const router = status.router_service || "unknown";
      document.getElementById("routerState").textContent = router;
      document.getElementById("routerDot").classList.toggle("active", router === "active");
      document.getElementById("configPath").textContent = status.config_path || "";
      document.getElementById("backupPath").textContent = status.backup_path || "";
      if (status.theme) applyTheme(status.theme);
    }

    async function loadConfig() {
      log("Loading configuration...");
      const response = await fetch("/api/config");
      const data = await response.json();
      if (!data.ok) throw new Error(data.message || "Config load failed");
      config = data.config;
      renderSection("ysf");
      renderSection("brandmeister");
      renderSection("behavior");
      renderRoutes();
      renderStatus(data.status);
      log("Configuration loaded.");
    }

    function collectSection(section) {
      const out = {};
      fields[section].forEach(([key, label, type]) => {
        const input = document.getElementById(inputId(section, key));
        if (type === "checkbox") out[key] = input.checked;
        else if (type === "number") out[key] = Number(input.value);
        else out[key] = input.value;
      });
      return out;
    }

    function collectRoutes() {
      const routes = [];
      document.querySelectorAll("#routes tr").forEach((row) => {
        const route = {};
        row.querySelectorAll("input").forEach((input) => {
          const key = input.dataset.routeKey;
          if (input.type === "checkbox") route[key] = input.checked;
          else if (input.type === "number") route[key] = Number(input.value);
          else route[key] = input.value;
        });
        routes.push(route);
      });
      return routes;
    }

    function collectConfig(restart) {
      return {
        ysf: collectSection("ysf"),
        brandmeister: collectSection("brandmeister"),
        behavior: collectSection("behavior"),
        routes: collectRoutes(),
        restart
      };
    }

    async function saveConfig(restart) {
      log(restart ? "Saving configuration and restarting router..." : "Saving configuration...");
      try {
        const response = await fetch("/api/config", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify(collectConfig(restart))
        });
        const data = await response.json();
        renderStatus(data.status || {});
        log(formatResult(data));
      } catch (error) {
        log(`Save failed: ${error}`);
      }
    }

    async function restartRouter() {
      log("Restarting router service...");
      const response = await fetch("/api/restart", {method: "POST"});
      const data = await response.json();
      renderStatus(data.status || {});
      log(formatResult(data));
    }

    function addRoute() {
      config.routes.push({
        enabled: true,
        dgid: 99,
        talkgroup: 9,
        short_name: "New",
        long_name: "New Talkgroup",
        region: "Custom",
        sort_order: 99
      });
      renderRoutes();
    }

    function formatResult(data) {
      const lines = [data.ok ? "OK" : "FAILED", data.message || ""];
      if (data.restart) {
        lines.push(data.restart.command || "");
        lines.push(`restart return code: ${data.restart.returncode}`);
        lines.push(`router service: ${data.restart.router_service}`);
        if (data.restart.stderr) lines.push(data.restart.stderr);
        if (data.restart.stdout) lines.push(data.restart.stdout);
      }
      return lines.filter(Boolean).join("\n");
    }

    loadTheme().finally(() => loadConfig().catch((error) => log(`Load failed: ${error}`)));
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
