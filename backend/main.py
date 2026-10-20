"""FastAPI backend for INCI Sight: label OCR, parsing, matching and serving."""
from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, Form, Header, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend import db
from dl_module.dl_service import analyze_label, parse_and_match

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("inci_sight")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "frontend" / "dist"

@asynccontextmanager
async def lifespan(_app):
    db.initialize_database()
    yield


app = FastAPI(title="INCI Sight API", version="1.0.0", description="Cosmetic ingredient OCR and personal watchlist screening.", lifespan=lifespan)


class ReviewPayload(BaseModel):
    text: str = Field(max_length=50000)
    avoid_list: list[str] = Field(default_factory=list, max_length=100)
    scan_id: int | None = None
    product_name: str = Field(default="", max_length=255)


class WatchlistPayload(BaseModel):
    ingredients: list[str] = Field(default_factory=list, max_length=100)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"code": code, "message": message}})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request, exc):
    return error_response(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request, _exc):
    return error_response(422, "invalid_request", "The request did not match the expected format.")


@app.exception_handler(Exception)
async def unexpected_error_handler(_request, exc):
    logger.exception("Unhandled backend error", exc_info=exc)
    return error_response(500, "server_error", "Something went wrong. Please try again.")


def image_format(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


async def read_limited(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("The image is larger than the 10 MB limit.")
    return data


def parse_avoid_list(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
        values = parsed if isinstance(parsed, list) else raw.split(",")
    except (json.JSONDecodeError, TypeError):
        values = raw.split(",")
    clean, seen = [], set()
    for item in values:
        name = re.sub(r"\s+", " ", str(item).strip())[:128]
        key = name.casefold()
        if name and key not in seen:
            clean.append(name)
            seen.add(key)
    return clean[:100]


def client_key(value: str | None) -> str:
    """Accept UUID browser IDs; hash a fallback token into a bounded DB key."""
    if not value:
        return "anonymous"
    try:
        return str(UUID(value))
    except (ValueError, AttributeError, TypeError):
        import hashlib
        return hashlib.sha256(value.encode("utf-8", "ignore")[:256]).hexdigest()


@app.get("/health")
def health():
    return {"success": True, "status": "healthy", "ocr": "EasyOCR (CPU)", "persistent_workspace": db.is_ready()}


@app.get("/api/info")
def info():
    return {"success": True, "name": "INCI Sight", "version": "1.0.0", "supported_formats": ["JPG", "JPEG", "PNG", "WEBP"], "max_upload_bytes": MAX_UPLOAD_BYTES, "ocr_engine": "EasyOCR", "persistent_workspace": db.is_ready()}


@app.get("/api/watchlist")
def get_watchlist(x_client_id: str | None = Header(default=None)):
    values = db.get_watchlist(client_key(x_client_id))
    return {"success": True, "persistent": values is not None, "ingredients": values or []}


@app.put("/api/watchlist")
def put_watchlist(payload: WatchlistPayload, x_client_id: str | None = Header(default=None)):
    values, seen = [], set()
    for raw in payload.ingredients:
        name = re.sub(r"\s+", " ", raw.strip())[:128]
        if len(name) >= 3 and name.casefold() not in seen:
            values.append(name)
            seen.add(name.casefold())
    saved = db.replace_watchlist(client_key(x_client_id), values)
    return {"success": True, "persistent": saved, "ingredients": values}


@app.get("/api/history")
def history(x_client_id: str | None = Header(default=None)):
    scans = db.recent_scans(client_key(x_client_id))
    return {"success": True, "persistent": scans is not None, "scans": scans or []}


@app.post("/api/analyze")
async def upload_label(
    file: UploadFile = File(...),
    avoid_list: str = Form("[]"),
    product_name: str = Form(""),
    x_client_id: str | None = Header(default=None),
):
    filename = (file.filename or "label").strip()[:255]
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return error_response(415, "unsupported_format", "Upload a JPG, JPEG, PNG, or WEBP image.")
    try:
        try:
            data = await read_limited(file)
        except ValueError as exc:
            return error_response(413, "file_too_large", str(exc))
    finally:
        await file.close()
    if not data:
        return error_response(400, "empty_file", "The uploaded image is empty.")
    detected = image_format(data)
    if detected is None or detected != ALLOWED_EXTENSIONS[extension]:
        return error_response(400, "invalid_image", "The image contents do not match the filename. Choose a valid JPG, PNG, or WEBP image.")
    try:
        selected = parse_avoid_list(avoid_list)
        result = await run_in_threadpool(analyze_label, data, selected)
    except ValueError as exc:
        return error_response(400, "analysis_error", str(exc))
    except Exception:
        logger.exception("EasyOCR label analysis failed")
        return error_response(500, "ocr_failed", "The label could not be read. Try a sharper, closer photo and scan again.")
    matches = result["matches"]
    scan_id = db.save_scan(client_key(x_client_id), product_name.strip()[:255], filename, result["extracted_text"], result["ingredients"], matches)
    return {
        "success": True,
        "file": {"filename": filename, "size_bytes": len(data), "detected_format": detected},
        "product_name": product_name.strip()[:255],
        "extracted_text": result["extracted_text"],
        "ingredients": result["ingredients"],
        "detections": result["detections"],
        "uncertain_text": result["uncertain_text"],
        "matches": matches,
        "vision_used": result.get("vision_used", False),
        "avoid_list": selected,
        "scan_id": scan_id,
        "persistent": db.is_ready(),
        "disclaimer": result["disclaimer"],
    }


@app.post("/api/review")
async def review(payload: ReviewPayload, x_client_id: str | None = Header(default=None)):
    try:
        result = await run_in_threadpool(parse_and_match, payload.text, payload.avoid_list)
    except ValueError as exc:
        return error_response(400, "review_error", str(exc))
    if payload.scan_id is not None:
        db.update_scan(client_key(x_client_id), payload.scan_id, payload.text, result["ingredients"], result["matches"])
    return {
        "success": True,
        "extracted_text": payload.text,
        "ingredients": result["ingredients"],
        "matches": result["matches"],
        "detections": [],
        "uncertain_text": [],
        "scan_id": payload.scan_id,
        "product_name": payload.product_name,
        "disclaimer": "Edited text is re-parsed locally by the backend. Verify every ingredient against the package.",
    }


@app.get("/")
def homepage():
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"success": True, "message": "INCI Sight API is running. Build the frontend for the web app."}


@app.get("/{path:path}")
def frontend_fallback(path: str):
    if path.startswith(("api/", "health")):
        return error_response(404, "not_found", "This route does not exist.")
    target = (STATIC_DIR / path).resolve()
    if STATIC_DIR.resolve() in target.parents and target.is_file():
        return FileResponse(target)
    index = STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return error_response(404, "not_found", "Build the frontend before requesting app pages.")
