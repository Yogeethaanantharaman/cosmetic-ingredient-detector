"""INCI Sight backend: API infrastructure only.

No OCR, no deep learning and no ingredient analysis lives here. The upload
endpoint only validates the file and returns its metadata; the image is read
into memory and discarded, never written to disk.
"""
import logging
import os

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("inci_sight")

APP_NAME = "INCI Sight"
APP_VERSION = "0.1.0"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}
ALLOWED_FORMATS = ["JPG", "JPEG", "PNG", "WEBP"]

# Vite dev server default is port 5173. Extra origins can be supplied via the
# CORS_ORIGINS environment variable (comma separated).
DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
ORIGINS = DEFAULT_ORIGINS + [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app = FastAPI(title=f"{APP_NAME} API", version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------- response models ----------
class StatusResponse(BaseModel):
    success: bool = True
    message: str


class HealthResponse(BaseModel):
    success: bool = True
    status: str


class FileMetadata(BaseModel):
    filename: str
    content_type: str | None
    size_bytes: int
    detected_format: str


class UploadResponse(BaseModel):
    success: bool = True
    message: str
    file: FileMetadata


# ---------- errors ----------
def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code, self.code, self.message = status_code, code, message


@app.exception_handler(APIError)
async def api_error_handler(_: Request, exc: APIError):
    return error_response(exc.status_code, exc.code, exc.message)


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_: Request, exc: StarletteHTTPException):
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    return error_response(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, __: RequestValidationError):
    return error_response(422, "invalid_request", "Invalid request. Send an image in the 'file' form field.")


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception):
    logger.exception("Unhandled error", exc_info=exc)  # details stay in server logs only
    return error_response(500, "server_error", "Something went wrong on the server. Please try again.")


# ---------- helpers ----------
def detect_image_format(data: bytes) -> str | None:
    """Identify the real image type from its leading bytes (no extra libraries)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


async def read_limited(upload: UploadFile) -> bytes:
    """Read the upload in chunks, stopping as soon as the size limit is exceeded."""
    chunks, total = [], 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise APIError(413, "file_too_large", "The image is larger than the 10 MB limit.")
        chunks.append(chunk)
    return b"".join(chunks)


# ---------- routes ----------
@app.get("/", response_model=StatusResponse)
def root():
    return {"success": True, "message": "INCI Sight backend is running"}


@app.get("/health", response_model=HealthResponse)
def health():
    return {"success": True, "status": "healthy"}


@app.get("/api/info")
def info():
    return {
        "success": True,
        "name": APP_NAME,
        "description": "Backend API for the INCI Sight cosmetic ingredient detector.",
        "version": APP_VERSION,
        "supported_formats": ALLOWED_FORMATS,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "endpoints": ["GET /", "GET /health", "GET /api/info", "POST /api/upload"],
    }


@app.post("/api/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise APIError(415, "unsupported_format", "Unsupported file type. Please upload a JPG, JPEG, PNG or WEBP image.")

    data = await read_limited(file)
    if not data:
        raise APIError(400, "empty_file", "The uploaded file is empty.")

    detected = detect_image_format(data)
    if detected is None or detected != ALLOWED_EXTENSIONS[ext]:
        raise APIError(400, "invalid_image", "The file is not a valid image of the type its extension claims.")

    # The image is intentionally not stored or analysed; only metadata is returned.
    return {
        "success": True,
        "message": "Image received and validated.",
        "file": {
            "filename": filename,
            "content_type": file.content_type,
            "size_bytes": len(data),
            "detected_format": detected,
        },
    }