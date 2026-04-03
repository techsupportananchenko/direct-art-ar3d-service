#!/usr/bin/env python3

import html
import json
import os
import re
import sys
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SERVICE_DIR = Path(__file__).resolve().parent
MONOREPO_ROOT = SERVICE_DIR.parent
INITIAL_ENV_KEYS = set(os.environ.keys())


def parse_env_value(value):
    trimmed = value.strip()
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {'"', "'"}:
        return trimmed[1:-1]
    return trimmed


def normalize_secret(value):
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) >= 2 and trimmed[0] == trimmed[-1] and trimmed[0] in {'"', "'"}:
        trimmed = trimmed[1:-1].strip()
    return trimmed or None


def resolve_existing_dir(raw_value):
    if not isinstance(raw_value, str):
        return None
    trimmed = raw_value.strip()
    if not trimmed:
        return None

    candidate = Path(trimmed).expanduser()
    if not candidate.is_absolute():
        candidate = SERVICE_DIR / candidate
    try:
        resolved = candidate.resolve()
    except OSError:
        return None

    return resolved if resolved.exists() else None


def load_env_file(path_obj):
    if not path_obj.exists():
        return

    try:
        lines = path_obj.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in INITIAL_ENV_KEYS:
            continue

        os.environ[key] = parse_env_value(value)


load_env_file(MONOREPO_ROOT / ".env")
load_env_file(MONOREPO_ROOT / ".env.local")
load_env_file(SERVICE_DIR / ".env")
load_env_file(SERVICE_DIR / ".env.local")

GENERATOR_MODULES_DIR = resolve_existing_dir(os.getenv("AR_SERVICE_GENERATOR_MODULES_DIR"))
if GENERATOR_MODULES_DIR is None:
    for candidate in (SERVICE_DIR / "Shopify", MONOREPO_ROOT / "Shopify"):
        if candidate.exists():
            GENERATOR_MODULES_DIR = candidate.resolve()
            break

if GENERATOR_MODULES_DIR and str(GENERATOR_MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(GENERATOR_MODULES_DIR))

GENERATOR_IMPORT_ERROR = None

try:
    from enhanced_ar_server import create_enhanced_3d_glb_from_image
    from enhanced_create_usdz import create_enhanced_3d_usdz_from_image
except Exception as error:
    GENERATOR_IMPORT_ERROR = error
    create_enhanced_3d_glb_from_image = None
    create_enhanced_3d_usdz_from_image = None

MODELS_DIR = Path(
    os.getenv("AR_SERVICE_MODELS_DIR")
    or SERVICE_DIR / "data" / "models"
)
PORT = int(os.getenv("AR_SERVICE_PORT") or os.getenv("PORT", "3003"))
SERVICE_TOKEN = normalize_secret(os.getenv("AR_GENERATOR_SERVICE_TOKEN")) or ""
PUBLIC_BASE_URL = (os.getenv("AR_SERVICE_PUBLIC_BASE_URL") or "").strip().rstrip("/")
RENDER_EXTERNAL_HOSTNAME = (os.getenv("RENDER_EXTERNAL_HOSTNAME") or "").strip()
DEFAULT_ARTWORK_SIZE_MM = 1000
MIN_GENERATED_FILE_SIZE_BYTES = 1000
DEFAULT_MODEL_DEPTH_MM = 8
MIN_MODEL_DEPTH_MM = 6
MAX_MODEL_DEPTH_MM = 12
FRAME_DEPTH_RATIO = 0.30
ARTWORK_DEPTH_PADDING_MM = 2
DEFAULT_ENHANCED_FEATURES = {
    "hasDepth": True,
    "hasSides": True,
    "hasBackPanel": True,
    "forwardTilt": "5°",
    "recessedArtwork": "2mm",
    "frameLip": "3mm",
    "backPanelColor": "dark brown cardboard",
}
MODEL_ROUTE_PATTERN = re.compile(r"^/api/ar/model/([^/]+)$")
MODEL_FILE_ROUTE_PATTERN = re.compile(r"^/api/ar/models/([^/]+)$")
SAFE_COLOR_PATTERN = re.compile(r"^[#(),.%\w\s-]+$")


def ensure_models_dir():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def get_generator_status():
    return {
        "ready": GENERATOR_IMPORT_ERROR is None,
        "modulesDir": str(GENERATOR_MODULES_DIR) if GENERATOR_MODULES_DIR else None,
        "error": str(GENERATOR_IMPORT_ERROR) if GENERATOR_IMPORT_ERROR else None,
    }


def normalize_origin(value):
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def resolve_cors_allow_origin(headers):
    origin = normalize_origin(headers.get("Origin"))
    if origin == "null":
        return "null"
    if isinstance(origin, str) and origin.startswith(("http://", "https://")):
        return origin
    return "*"


def to_finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def first_finite_number(*values):
    for value in values:
        number = to_finite_number(value)
        if number is not None:
            return number
    return None


def clamp_number(value, min_value, max_value):
    return min(max_value, max(min_value, value))


def read_finite_query_value(query, key):
    values = query.get(key) or []
    return first_finite_number(values[0] if values else None)


def read_color_query_value(query, key, fallback):
    values = query.get(key) or []
    value = values[0] if values else None
    if not isinstance(value, str) or not value:
        return fallback
    return value if SAFE_COLOR_PATTERN.match(value) else fallback


def is_authorized(headers, method, route_path):
    if method in {"GET", "HEAD", "OPTIONS"}:
        return True

    if not SERVICE_TOKEN:
        return True

    auth_header = headers.get("Authorization") or ""
    auth_token = None
    if isinstance(auth_header, str):
        parts = auth_header.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            auth_token = normalize_secret(parts[1])

    if auth_token == SERVICE_TOKEN:
        return True
    if normalize_secret(headers.get("X-AR-Service-Token")) == SERVICE_TOKEN:
        return True

    return False


def resolve_frame_width_mm(frame_data):
    return (
        first_finite_number(
            frame_data.get("width_mm") if isinstance(frame_data, dict) else None,
            frame_data.get("faceWidthMm") if isinstance(frame_data, dict) else None,
            frame_data.get("face_width_mm") if isinstance(frame_data, dict) else None,
            frame_data.get("widthMm") if isinstance(frame_data, dict) else None,
        )
        or 24
    )


def resolve_artwork_depth_mm(artwork_data):
    artwork_data = artwork_data if isinstance(artwork_data, dict) else {}
    return first_finite_number(
        artwork_data.get("depth_mm"),
        artwork_data.get("depthMm"),
        first_finite_number(artwork_data.get("depth_inches")) * 25.4
        if first_finite_number(artwork_data.get("depth_inches")) is not None
        else None,
        first_finite_number(artwork_data.get("depthInches")) * 25.4
        if first_finite_number(artwork_data.get("depthInches")) is not None
        else None,
        artwork_data.get("productDepthMm"),
    )


def resolve_frame_depth_mm(frame_data):
    frame_data = frame_data if isinstance(frame_data, dict) else {}
    return first_finite_number(
        frame_data.get("depth_mm"),
        frame_data.get("depthMm"),
        frame_data.get("profile_depth_mm"),
        frame_data.get("profileDepthMm"),
        frame_data.get("rabbet_depth_mm"),
        frame_data.get("rabbetDepthMm"),
        frame_data.get("frameDepthMm"),
    )


def resolve_model_depth_mm(frame_data, artwork_data):
    frame_width_mm = resolve_frame_width_mm(frame_data or {})
    explicit_frame_depth_mm = resolve_frame_depth_mm(frame_data or {})
    artwork_depth_mm = resolve_artwork_depth_mm(artwork_data or {})

    derived_frame_depth_mm = (
        explicit_frame_depth_mm
        if explicit_frame_depth_mm is not None
        else clamp_number(
            frame_width_mm * FRAME_DEPTH_RATIO,
            MIN_MODEL_DEPTH_MM,
            MAX_MODEL_DEPTH_MM,
        )
    )

    padded_artwork_depth_mm = (
        clamp_number(
            artwork_depth_mm + ARTWORK_DEPTH_PADDING_MM,
            MIN_MODEL_DEPTH_MM,
            MAX_MODEL_DEPTH_MM,
        )
        if artwork_depth_mm is not None
        else None
    )

    chosen_depth_mm = first_finite_number(
        padded_artwork_depth_mm,
        derived_frame_depth_mm,
        DEFAULT_MODEL_DEPTH_MM,
    )

    return clamp_number(chosen_depth_mm, MIN_MODEL_DEPTH_MM, MAX_MODEL_DEPTH_MM)


def resolve_artwork_dimensions(artwork_data):
    artwork_data = artwork_data if isinstance(artwork_data, dict) else {}
    width_mm = first_finite_number(
        artwork_data.get("calculated_width_mm"),
        artwork_data.get("width_mm"),
        artwork_data.get("widthMm"),
    )
    height_mm = first_finite_number(
        artwork_data.get("calculated_height_mm"),
        artwork_data.get("height_mm"),
        artwork_data.get("heightMm"),
    )
    explicit_aspect = (
        first_finite_number(
            artwork_data.get("natural_aspect"),
            artwork_data.get("aspectRatio"),
            artwork_data.get("aspect_ratio"),
        )
        or (width_mm / height_mm if width_mm and height_mm else None)
        or 1
    )
    safe_aspect = explicit_aspect if explicit_aspect > 0 else 1

    if width_mm and not height_mm:
        height_mm = width_mm / safe_aspect
    elif not width_mm and height_mm:
        width_mm = height_mm * safe_aspect
    elif not width_mm and not height_mm:
        if safe_aspect >= 1:
            width_mm = DEFAULT_ARTWORK_SIZE_MM
            height_mm = DEFAULT_ARTWORK_SIZE_MM / safe_aspect
        else:
            height_mm = DEFAULT_ARTWORK_SIZE_MM
            width_mm = DEFAULT_ARTWORK_SIZE_MM * safe_aspect

    return {"widthMm": width_mm, "heightMm": height_mm}


def get_model_dimensions(frame_data, artwork_data):
    frame_width_mm = resolve_frame_width_mm(frame_data or {})
    artwork_dimensions = resolve_artwork_dimensions(artwork_data or {})
    depth_mm = resolve_model_depth_mm(frame_data or {}, artwork_data or {})
    total_width_mm = artwork_dimensions["widthMm"] + frame_width_mm * 2
    total_height_mm = artwork_dimensions["heightMm"] + frame_width_mm * 2

    return {
        "frameWidthMm": frame_width_mm,
        "artworkWidthMm": artwork_dimensions["widthMm"],
        "artworkHeightMm": artwork_dimensions["heightMm"],
        "totalWidthMm": total_width_mm,
        "totalHeightMm": total_height_mm,
        "widthMeters": total_width_mm / 1000,
        "heightMeters": total_height_mm / 1000,
        "depthMeters": depth_mm / 1000,
    }


def build_public_base_url(handler):
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL

    if RENDER_EXTERNAL_HOSTNAME:
        return f"https://{RENDER_EXTERNAL_HOSTNAME}"

    forwarded_host = normalize_origin(handler.headers.get("X-Forwarded-Host"))
    forwarded_proto = normalize_origin(handler.headers.get("X-Forwarded-Proto"))
    if forwarded_host:
        return f"{forwarded_proto or 'https'}://{forwarded_host}"

    host = normalize_origin(handler.headers.get("Host")) or f"localhost:{PORT}"
    return f"{forwarded_proto or 'http'}://{host}"


def build_public_file_url(handler, model_id, file_type):
    base_url = build_public_base_url(handler)
    return f"{base_url}/api/ar/models/{model_id}?fileType={file_type}"


def with_public_urls(handler, model):
    if not isinstance(model, dict):
        return model

    model_id = model.get("modelId") or model.get("id")
    if not model_id:
        return model

    normalized = dict(model)
    base_url = build_public_base_url(handler)
    normalized["glbUrl"] = build_public_file_url(handler, model_id, "glb")
    normalized["usdzUrl"] = build_public_file_url(handler, model_id, "usdz")
    normalized["viewerUrl"] = f"{base_url}/ar-viewer?modelId={model_id}"
    return normalized


def build_ar_viewer_html(model, embed, theme):
    title = html.escape(model.get("title") or "Framed Artwork")
    frame_name = html.escape(model.get("frameName") or "Selected Frame")
    glb_url = html.escape(model.get("glbUrl") or "")
    usdz_url = html.escape(model.get("usdzUrl") or "")
    width_inches = first_finite_number(model.get("dimensions", {}).get("width_inches"))
    height_inches = first_finite_number(model.get("dimensions", {}).get("height_inches"))

    size_label = (
        f'{width_inches:.1f}" x {height_inches:.1f}"'
        if width_inches is not None and height_inches is not None
        else "Unknown size"
    )
    page_padding = "0" if embed else "24px 16px 40px"
    container_gap = "0" if embed else "18px"
    section_radius = "0" if embed else "20px"
    section_padding = "0" if embed else "14px"
    section_shadow = "none" if embed else "0 18px 50px rgba(15, 23, 42, 0.08)"
    section_min_height = "100vh" if embed else "auto"
    section_background = (
        "transparent"
        if embed
        else "linear-gradient(180deg, var(--ar-viewer-page-bg) 0%, var(--ar-viewer-page-bg-alt) 100%)"
    )
    model_height = "100vh" if embed else "min(72vh, 620px)"

    header_html = ""
    info_html = ""

    if not embed:
        header_html = f"""
          <header style="display:flex;align-items:center;justify-content:space-between;gap:16px;">
            <div>
              <h1 style="margin:0;font-size:28px;line-height:1.1;">View in AR</h1>
              <p style="margin:6px 0 0;color:var(--ar-viewer-text-muted-color);">{title}</p>
            </div>
            <button
              type="button"
              onclick="window.close()"
              style="border:1px solid var(--ar-viewer-border-color);background:var(--ar-viewer-surface-color);border-radius:999px;padding:10px 14px;cursor:pointer;color:var(--ar-viewer-text-color);"
            >
              Close
            </button>
          </header>
        """
        info_html = f"""
          <section
            style="background:var(--ar-viewer-surface-color);border-radius:20px;padding:18px 20px;box-shadow:0 18px 50px rgba(15, 23, 42, 0.08);display:grid;gap:10px;"
          >
            <div style="font-size:15px;color:var(--ar-viewer-text-muted-color);">Size: {html.escape(size_label)}</div>
            <div style="font-size:15px;color:var(--ar-viewer-text-muted-color);">Frame: {frame_name}</div>
            <div style="font-size:14px;color:var(--ar-viewer-text-muted-color);">
              On iPhone/iPad Safari use native AR Quick Look. On desktop and Android this page shows the generated 3D model.
            </div>
          </section>
        """

    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>AR Viewer</title>
    <style>
      :root {{
        --ar-viewer-page-bg: {theme["pageBg"]};
        --ar-viewer-page-bg-alt: {theme["pageBgAlt"]};
        --ar-viewer-surface-color: {theme["surfaceColor"]};
        --ar-viewer-text-color: {theme["textColor"]};
        --ar-viewer-text-muted-color: {theme["textMutedColor"]};
        --ar-viewer-border-color: {theme["borderColor"]};
      }}

      html,
      body {{
        margin: 0;
        padding: 0;
        min-height: 100%;
        background: linear-gradient(180deg, var(--ar-viewer-page-bg) 0%, var(--ar-viewer-page-bg-alt) 100%);
        color: var(--ar-viewer-text-color);
        overflow: hidden;
        font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
      }}

      body {{
        min-height: 100vh;
      }}
    </style>
    <script type="module" src="https://unpkg.com/@google/model-viewer/dist/model-viewer.min.js"></script>
  </head>
  <body>
    <main
      style="min-height:100vh;margin:0;padding:{page_padding};color:var(--ar-viewer-text-color);font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;overflow:hidden;"
    >
      <div
        style="max-width:{'100%' if embed else '720px'};margin:0 auto;display:grid;gap:{container_gap};min-height:100vh;"
      >
        {header_html}
        <section
          style="border-radius:{section_radius};padding:{section_padding};box-shadow:{section_shadow};min-height:{section_min_height};background:{section_background};"
        >
          <model-viewer
            src="{glb_url or ''}"
            alt="Framed artwork 3D model"
            auto-rotate
            camera-controls
            shadow-intensity="1"
            {'ar' if usdz_url else ''}
            {'ios-src="' + usdz_url + '"' if usdz_url else ''}
            style="display:block;width:100%;height:{model_height};background:transparent;"
          ></model-viewer>
        </section>
        {info_html}
      </div>
    </main>
  </body>
</html>"""


def build_metadata(handler, model_id, frame_data, artwork_data):
    dimensions = get_model_dimensions(frame_data, artwork_data)
    base_url = build_public_base_url(handler)
    return {
        "id": model_id,
        "modelId": model_id,
        "title": (
            (artwork_data or {}).get("title")
            or (artwork_data or {}).get("name")
            or (artwork_data or {}).get("productTitle")
            or "Framed Artwork"
        ),
        "frameName": (
            (frame_data or {}).get("name")
            or (frame_data or {}).get("id")
            or (frame_data or {}).get("moulding_web_id")
            or "Selected Frame"
        ),
        "dimensions": {
            "width_mm": dimensions["totalWidthMm"],
            "height_mm": dimensions["totalHeightMm"],
            "width_inches": dimensions["totalWidthMm"] / 25.4,
            "height_inches": dimensions["totalHeightMm"] / 25.4,
            "depth_mm": dimensions["depthMeters"] * 1000,
            "depth_inches": (dimensions["depthMeters"] * 1000) / 25.4,
        },
        "frameData": frame_data,
        "artworkData": artwork_data,
        "enhancedFeatures": DEFAULT_ENHANCED_FEATURES,
        "glbUrl": build_public_file_url(handler, model_id, "glb"),
        "usdzUrl": build_public_file_url(handler, model_id, "usdz"),
        "viewerUrl": f"{base_url}/ar-viewer?modelId={model_id}",
    }


def get_model_glb_path(model_id):
    return MODELS_DIR / f"{model_id}.glb"


def get_model_usdz_path(model_id):
    return MODELS_DIR / f"{model_id}.usdz"


def get_model_metadata_path(model_id):
    return MODELS_DIR / f"{model_id}.json"


def write_json_file(path_obj, payload):
    path_obj.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")


def read_json_file(path_obj):
    return json.loads(path_obj.read_text(encoding="utf-8"))


def validate_generated_file(path_obj, label):
    if not path_obj.exists():
        raise RuntimeError(f"{label} file not found")
    if path_obj.stat().st_size <= MIN_GENERATED_FILE_SIZE_BYTES:
        raise RuntimeError(f"{label} file too small: {path_obj.stat().st_size} bytes")


class ARGeneratorRequestHandler(BaseHTTPRequestHandler):
    server_version = "ARGeneratorService/1.0"

    def log_message(self, format_string, *args):
        sys.stderr.write("[ar-generator-service] " + format_string % args + "\n")

    def end_headers(self):
        allow_origin = resolve_cors_allow_origin(self.headers)
        self.send_header("Access-Control-Allow-Origin", allow_origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept, Authorization, X-AR-Service-Token")
        self.send_header("Access-Control-Max-Age", "86400")
        super().end_headers()

    def send_json(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_html(self, status_code, markup):
        body = markup.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file(self, path_obj, content_type):
        body = path_obj.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Content-Disposition", f'inline; filename="{path_obj.name}"')
        self.send_header("Cross-Origin-Resource-Policy", "cross-origin")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length else b""
        try:
            return json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body")

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_HEAD(self):
        self.handle_request()

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        ensure_models_dir()
        parsed_url = urlparse(self.path)
        route_path = parsed_url.path

        if not is_authorized(self.headers, self.command, route_path):
            self.send_json(401, {"error": "Unauthorized"})
            return

        if self.command in {"GET", "HEAD"} and route_path == "/health":
            health_payload = {"ok": True, "generator": get_generator_status()}
            self.send_json(200, health_payload)
            return

        if self.command in {"GET", "HEAD"} and route_path == "/ar-viewer":
            self.handle_ar_viewer(parsed_url.query)
            return

        if self.command == "POST" and route_path == "/api/ar/generate-model":
            self.handle_generate_model()
            return

        model_match = MODEL_ROUTE_PATTERN.match(route_path)
        if self.command in {"GET", "HEAD"} and model_match:
            self.handle_get_model(model_match.group(1))
            return

        model_file_match = MODEL_FILE_ROUTE_PATTERN.match(route_path)
        if self.command in {"GET", "HEAD"} and model_file_match:
            self.handle_get_model_file(model_file_match.group(1), parsed_url.query)
            return

        self.send_json(404, {"error": "Not found"})

    def handle_ar_viewer(self, raw_query):
        query = parse_qs(raw_query or "")
        model_id = (query.get("modelId") or [None])[0]
        if not model_id:
            self.send_html(400, "<h1>No model ID provided</h1>")
            return

        metadata_path = get_model_metadata_path(model_id)
        if not metadata_path.exists():
            self.send_html(404, "<h1>AR model not found</h1>")
            return

        try:
            model = read_json_file(metadata_path)
        except Exception as error:
            self.send_html(500, f"<h1>Failed to read AR model: {html.escape(str(error))}</h1>")
            return

        model = with_public_urls(self, model)

        embed = (query.get("embed") or ["0"])[0] == "1"
        theme = {
            "pageBg": read_color_query_value(query, "pageBg", "#F7F5F0" if embed else "#F8FAFC"),
            "pageBgAlt": read_color_query_value(query, "pageBgAlt", "#ECE8DD" if embed else "#E2E8F0"),
            "surfaceColor": read_color_query_value(query, "surfaceColor", "#FFFFFF"),
            "textColor": read_color_query_value(query, "textColor", "#1F2933"),
            "textMutedColor": read_color_query_value(query, "textMutedColor", "#52606D"),
            "borderColor": read_color_query_value(query, "borderColor", "#CBD2D9"),
        }

        model["title"] = (query.get("title") or [model.get("title")])[0]
        model["frameName"] = (query.get("frameName") or [model.get("frameName")])[0]
        dimensions = model.get("dimensions") or {}
        width_inches = read_finite_query_value(query, "widthInches")
        height_inches = read_finite_query_value(query, "heightInches")
        depth_inches = read_finite_query_value(query, "depthInches")
        if width_inches is not None:
            dimensions["width_inches"] = width_inches
        if height_inches is not None:
            dimensions["height_inches"] = height_inches
        if depth_inches is not None:
            dimensions["depth_inches"] = depth_inches
        model["dimensions"] = dimensions

        self.send_html(200, build_ar_viewer_html(model, embed, theme))

    def handle_generate_model(self):
        if GENERATOR_IMPORT_ERROR is not None:
            status = get_generator_status()
            self.send_json(
                503,
                {
                    "error": "AR generator modules are not available",
                    "details": status["error"],
                    "generatorModulesDir": status["modulesDir"],
                },
            )
            return

        try:
            payload = self.read_json_body()
        except ValueError as error:
            self.send_json(400, {"error": str(error)})
            return

        image_data = payload.get("imageData")
        frame_data = payload.get("frameData")
        artwork_data = payload.get("artworkData")

        if not image_data or not isinstance(frame_data, dict) or not isinstance(artwork_data, dict):
            self.send_json(
                400,
                {"error": "Missing required data: imageData, frameData, artworkData"},
            )
            return

        model_id = str(uuid.uuid4())
        glb_path = get_model_glb_path(model_id)
        usdz_path = get_model_usdz_path(model_id)
        metadata_path = get_model_metadata_path(model_id)

        try:
            dimensions = get_model_dimensions(frame_data, artwork_data)
            glb_bytes = create_enhanced_3d_glb_from_image(
                image_data,
                dimensions["widthMeters"],
                dimensions["heightMeters"],
                dimensions["depthMeters"],
            )
            usdz_bytes = create_enhanced_3d_usdz_from_image(
                image_data,
                dimensions["widthMeters"],
                dimensions["heightMeters"],
                dimensions["depthMeters"],
            )

            glb_path.write_bytes(glb_bytes)
            usdz_path.write_bytes(usdz_bytes)
            validate_generated_file(glb_path, "GLB")
            validate_generated_file(usdz_path, "USDZ")

            metadata = build_metadata(self, model_id, frame_data, artwork_data)
            write_json_file(metadata_path, metadata)
            self.send_json(200, {"success": True, "data": metadata})
        except Exception as error:
            for path_obj in (glb_path, usdz_path, metadata_path):
                try:
                    if path_obj.exists():
                        path_obj.unlink()
                except OSError:
                    pass
            self.send_json(
                500,
                {
                    "error": "Failed to generate AR model",
                    "details": str(error),
                },
            )

    def handle_get_model(self, model_id):
        metadata_path = get_model_metadata_path(model_id)
        if not metadata_path.exists():
            self.send_json(404, {"error": "AR model not found"})
            return

        try:
            metadata = read_json_file(metadata_path)
        except Exception as error:
            self.send_json(500, {"error": f"Failed to read model metadata: {error}"})
            return

        metadata = with_public_urls(self, metadata)
        self.send_json(200, metadata)

    def handle_get_model_file(self, model_id, raw_query):
        query = parse_qs(raw_query or "")
        file_type = (query.get("fileType") or [None])[0]
        file_path = None
        content_type = "application/octet-stream"

        if file_type == "glb":
            file_path = get_model_glb_path(model_id)
            content_type = "model/gltf-binary"
        elif file_type == "usdz":
            file_path = get_model_usdz_path(model_id)
            content_type = "model/vnd.usdz+zip"

        if file_path is None:
            self.send_json(400, {"error": "Missing modelId or fileType"})
            return

        if not file_path.exists():
            self.send_json(404, {"error": "Model file not found"})
            return

        self.send_file(file_path, content_type)


def main():
    ensure_models_dir()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ARGeneratorRequestHandler)
    print(
        f"[ar-generator-service] listening on http://0.0.0.0:{PORT} "
        f"(models dir: {MODELS_DIR})"
    )
    if GENERATOR_IMPORT_ERROR is not None:
        print(
            "[ar-generator-service] generator modules unavailable: "
            f"{GENERATOR_IMPORT_ERROR}",
            file=sys.stderr,
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
