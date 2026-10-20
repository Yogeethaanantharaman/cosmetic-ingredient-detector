"""Vision-first extraction of cosmetic INCI ingredients.

The image is sent transiently to Manus's OpenAI-compatible vision endpoint and
is requested as strict JSON. OCR remains responsible for source text and
confidence display; this module is the primary ingredient-list extractor.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger("inci_sight.vision")

VISION_MODEL = os.getenv("INCI_VISION_MODEL", "gpt-5-mini")
VISION_TIMEOUT_SECONDS = 90
MAX_INGREDIENTS = 150
VISION_PROSE_WORDS = {
    "apply", "daily", "directions", "hair", "healthy", "ingredients",
    "keep", "made", "now", "nourished", "product", "reality", "strong",
    "usage", "warning", "warnings", "with",
}

SYSTEM_PROMPT = (
    "You extract cosmetic INCI ingredients from package photos. "
    "Return only ingredients that belong to the formal ingredient list. "
    "Ignore slogans, product claims, directions, warnings, usage instructions, "
    "brand names, addresses, certifications, symbols, batch codes, and every "
    "other non-ingredient text. Preserve the visible label order. Never invent "
    "or infer an ingredient that is not visible. If no formal ingredient list "
    "is visible, return an empty array."
)


def _mime_type(image_format: str) -> str:
    return {
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }.get(image_format, "application/octet-stream")


def _request_body(image_bytes: bytes, image_format: str, ocr_text: str = "") -> dict:
    data_url = (
        f"data:{_mime_type(image_format)};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )
    return {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Read this cosmetic label and return JSON with an "
                            "ingredients array only. The following OCR is only "
                            "secondary evidence; use the image to decide which "
                            "words belong to the formal INCI section and ignore "
                            "all preceding marketing copy:\n\n"
                            f"{ocr_text[:12000]}"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url, "detail": "high"},
                    },
                ],
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ingredient_list",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "ingredients": {
                            "type": "array",
                            "items": {"type": "string"},
                        }
                    },
                    "required": ["ingredients"],
                    "additionalProperties": False,
                },
            },
        },
        "reasoning": {"effort": "minimal"},
        "max_completion_tokens": 4000,
    }


def _clean_ingredients(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("Vision response did not contain an ingredient array.")

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in value[:MAX_INGREDIENTS]:
        if not isinstance(raw, str):
            continue
        name = " ".join(raw.split()).strip(" .:;-\t")
        words = {word.casefold() for word in name.replace("/", " ").split()}
        if (
            not name
            or len(name) > 128
            or any(char in name for char in ".!?\n")
            or words & VISION_PROSE_WORDS
        ):
            continue
        key = name.casefold()
        if key not in seen:
            cleaned.append(name)
            seen.add(key)
    return cleaned


def _content_from_response(response: dict) -> str:
    if response.get("error"):
        raise ValueError(str(response["error"].get("message", "Vision service error.")))
    choices = response.get("choices") or []
    content = ((choices[0].get("message") or {}).get("content") if choices else None)
    if not content:
        raise ValueError("Vision service returned no structured content.")
    return content


def extract_ingredients_from_image(
    image_bytes: bytes,
    image_format: str,
    ocr_text: str = "",
) -> list[str]:
    """Return only visually identified INCI names, or raise on service failure."""
    api_url = os.getenv("MANUS_API_URL")
    api_key = os.getenv("MANUS_API_KEY")
    if not api_url or not api_key:
        raise RuntimeError("Managed vision service credentials are unavailable.")

    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(_request_body(image_bytes, image_format, ocr_text)).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=VISION_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"Vision service request failed: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Vision service returned invalid JSON.") from exc

    content = _content_from_response(payload)
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Vision service returned non-JSON ingredient data.") from exc
    return _clean_ingredients(parsed.get("ingredients"))
