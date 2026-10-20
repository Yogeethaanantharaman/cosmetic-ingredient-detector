
import logging
import time

import cv2
import easyocr
import numpy as np
import torch

from dl_module.preprocessing import preprocess_image

logger = logging.getLogger("inci_sight.ocr")

# Limit CPU threads to avoid excessive thread overhead.
# This may improve speed on some computers.
try:
    torch.set_num_threads(4)
except Exception:
    pass

# Keep the OCR model in memory between uploads.
_reader = None


def get_reader():
    global _reader

    if _reader is None:
        start = time.perf_counter()

        _reader = easyocr.Reader(
            ["en"],
            gpu=False,
            verbose=False,
        )

        logger.info(
            "EasyOCR model loaded in %.2f seconds",
            time.perf_counter() - start,
        )

    return _reader


def _sort_reading_order(results):
    """Sort text detections approximately from top to bottom."""
    if not results:
        return []

    return sorted(
        results,
        key=lambda item: (
            sum(point[1] for point in item[0])
            / len(item[0]),
            min(point[0] for point in item[0]),
        ),
    )


def _needs_retry(results):
    """
    Retry if the first OCR result contains too little text.
    A missing heading alone does not force a second pass.
    """
    if len(results) < 8:
        return True

    combined_text = " ".join(
        str(item[1]).strip()
        for item in results
    )

    letter_count = sum(
        character.isalpha()
        for character in combined_text
    )

    return letter_count < 60


def _enhance_contrast(image):
    """Create a grayscale contrast-enhanced fallback image."""
    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY,
    )

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    enhanced = clahe.apply(gray)

    return cv2.cvtColor(
        enhanced,
        cv2.COLOR_GRAY2BGR,
    )


def _run_ocr(reader, image):
    """Run a single OCR pass with a reduced processing canvas."""
    return reader.readtext(
        image,
        detail=1,
        paragraph=False,
        decoder="greedy",
        batch_size=1,
        workers=0,
        canvas_size=1400,
        mag_ratio=1.0,
        min_size=8,
        text_threshold=0.6,
        low_text=0.3,
        link_threshold=0.4,
    )


def _result_score(results):
    """Score OCR results using text amount, confidence and heading evidence."""
    if not results:
        return 0.0

    text = " ".join(
        str(item[1]).strip()
        for item in results
        if str(item[1]).strip()
    )

    if not text:
        return 0.0

    normalized = text.casefold()

    letter_count = sum(
        character.isalpha()
        for character in text
    )

    average_confidence = sum(
        float(item[2])
        for item in results
    ) / len(results)

    score = letter_count * (
        0.45 + 0.55 * average_confidence
    )

    heading_markers = (
        "ingredients",
        "ingredient",
        "ingredlents",
        "ingred1ents",
        "inci",
    )

    if any(
        marker in normalized
        for marker in heading_markers
    ):
        score += 100

    return score


def extract_text(image_bytes: bytes) -> dict:
    """Extract label text using one OCR pass and a conditional retry."""
    if not image_bytes:
        raise ValueError("The uploaded image is empty.")

    start = time.perf_counter()

    image = preprocess_image(image_bytes)

    preprocessing_seconds = (
        time.perf_counter() - start
    )

    reader = get_reader()

    ocr_start = time.perf_counter()

    # First attempt: recognize the original image.
    results = _sort_reading_order(
        _run_ocr(reader, image)
    )

    selected_variant = "original"

    logger.info(
        "First OCR pass detected %d text regions",
        len(results),
    )

    # Only run a second pass when the result looks incomplete.
    if _needs_retry(results):
        logger.info(
            "OCR result is short; trying contrast enhancement"
        )

        enhanced = _enhance_contrast(image)

        retry_results = _sort_reading_order(
            _run_ocr(reader, enhanced)
        )

        # Compare results rather than blindly replacing the first result.
        if _result_score(retry_results) > _result_score(results):
            results = retry_results
            selected_variant = "contrast"

    ocr_seconds = time.perf_counter() - ocr_start

    detections = []
    uncertain_text = []
    recognized_lines = []

    for _box, text, confidence in results:
        text = str(text).strip()

        if not text:
            continue

        confidence = round(
            float(confidence),
            3,
        )

        detection = {
            "text": text,
            "confidence": confidence,
        }

        detections.append(detection)
        recognized_lines.append(text)

        if confidence < 0.50:
            uncertain_text.append(detection)

    extracted_text = "\n".join(
        recognized_lines
    )

    logger.info(
        "OCR finished: variant=%s, detections=%d, "
        "preprocessing=%.2fs, recognition=%.2fs",
        selected_variant,
        len(detections),
        preprocessing_seconds,
        ocr_seconds,
    )

    return {
        "extracted_text": extracted_text,
        "detections": detections,
        "uncertain_text": uncertain_text,
        "timings": {
            "preprocessing_seconds": round(
                preprocessing_seconds,
                2,
            ),
            "ocr_seconds": round(
                ocr_seconds,
                2,
            ),
            "selected_variant": selected_variant,
        },
    }
