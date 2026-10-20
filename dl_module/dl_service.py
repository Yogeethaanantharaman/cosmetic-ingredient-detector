
import logging

from dl_module.ocr_service import extract_text
from dl_module.ingredient_extractor import extract_ingredients
from dl_module.ingredient_matcher import find_avoid_matches, normalize_text
from dl_module.vision_extractor import extract_ingredients_from_image

logger = logging.getLogger("inci_sight.analysis")


def _image_format(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "webp"
    raise ValueError("Unable to determine the uploaded image format.")


def _reconcile_names(vision_names: list[str], ocr_names: list[str]) -> list[str]:
    """Use vision to filter OCR candidates, retaining OCR names and order."""
    if not ocr_names:
        return vision_names

    vision_tokens = [set(normalize_text(name).split()) for name in vision_names]
    selected = []
    for ocr_name in ocr_names:
        ocr_normalized = normalize_text(ocr_name)
        ocr_tokens = set(ocr_normalized.split())
        matched = False
        for tokens, vision_name in zip(vision_tokens, vision_names):
            vision_normalized = normalize_text(vision_name)
            if (
                ocr_normalized in vision_normalized
                or vision_normalized in ocr_normalized
                or (tokens and ocr_tokens and len(tokens & ocr_tokens) / min(len(tokens), len(ocr_tokens)) >= 0.6)
            ):
                matched = True
                break
        if matched:
            selected.append(ocr_name)

    # If the model could not see enough of the list, the conservative OCR
    # parser is safer than returning a partial list presented as complete.
    minimum = max(1, round(len(ocr_names) * 0.5))
    return selected if len(selected) >= minimum else ocr_names


def parse_and_match(extracted_text: str, avoid_list: list[str]) -> dict:
    """Parse all candidate names and attach each watchlist match to a label item."""
    ingredients = extract_ingredients(extracted_text)
    matches = []
    for detected in ingredients:
        for match in find_avoid_matches(detected, avoid_list):
            matches.append({
                **match,
                "detected_ingredient": detected,
                "message": f"{match['ingredient']} matched {detected} on the label.",
            })
    return {"ingredients": ingredients, "matches": matches}


def analyze_label(
    image_bytes: bytes,
    avoid_list: list[str],
) -> dict:
    """
    Analyze a cosmetic ingredient label.

    Returns:
    - OCR extracted text
    - Parsed ingredient candidates
    - Matches against user's avoid-list
    - OCR confidence information
    """

    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    # OCR remains the user-visible source text and confidence signal.
    ocr = extract_text(image_bytes)

    extracted_text = ocr["extracted_text"]

    # The image model is the primary extractor: it can distinguish an INCI
    # block from slogans, claims, directions, and address text. If the managed
    # vision service is unavailable, keep the app usable with the conservative
    # OCR parser rather than returning unvalidated OCR fragments.
    vision_used = False
    import os
    try:
        if not (os.getenv("MANUS_API_URL") and os.getenv("MANUS_API_KEY")):
            raise RuntimeError("Vision service not configured")
        vision_names = extract_ingredients_from_image(
            image_bytes,
            _image_format(image_bytes),
            extracted_text,
        )
        ingredients = _reconcile_names(vision_names, extract_ingredients(extracted_text))
        vision_used = True
    except Exception:
        logger.warning("Vision unavailable; using OCR ingredient parser")
        ingredients = extract_ingredients(extracted_text)

    matches = []
    for detected in ingredients:
        for match in find_avoid_matches(detected, avoid_list):
            matches.append({
                **match,
                "detected_ingredient": detected,
                "message": f"{match['ingredient']} matched {detected} on the label.",
            })
    parsed = {"ingredients": ingredients, "matches": matches}

    return {
        "extracted_text": extracted_text,
        "ingredients": parsed["ingredients"],
        "matches": parsed["matches"],
        "detections": ocr["detections"],
        "uncertain_text": ocr["uncertain_text"],
        "matched_ingredients": parsed["matches"],
        "vision_used": vision_used,
        "disclaimer": (
            "Vision extraction, OCR, and ingredient matching are screening aids. "
            "Verify uncertain readings against the product label. "
            "A missing match does not guarantee safety."
        ),
    }
