# INCI Sight — implementation plan

## Product and architecture

Implement the supplied cosmetic ingredient detector as one deployable web product. A React/Vite single-page frontend is served by a FastAPI application on port 3000; the browser sends image uploads to the backend, which validates the file, preprocesses it with OpenCV, runs the supplied EasyOCR recognition model, parses its recognized label text into an ordered ingredient list, and applies the supplied exact/synonym/family matching rules to the user's watchlist. Results show all parsed candidates, the source OCR text, low-confidence OCR segments, and watchlist matches. The user can correct the OCR text and reparse it without uploading again.

Use the source project modules `dl_module/preprocessing.py`, `ocr_service.py`, `ingredient_extractor.py`, `ingredient_matcher.py`, and `dl_service.py` as the starting point; repair the API shape so it returns all ingredients, not only watchlist matches. Never invent ingredient safety classifications or functions absent from the source. The user watchlist is the source of personal alerts. Persistence uses the approved managed MySQL feature for a browser-scoped anonymous workspace and scan history, with browser local storage as a graceful fallback when a database connection is unavailable. No uploaded-image object storage was selected, so images are processed transiently and not persisted.

## Project structure

- `backend/main.py`: FastAPI routes, upload validation, analysis/review and health endpoints; serves the built web app.
- `backend/db.py`: additive MySQL schema and browser-workspace watchlist/scan persistence.
- `dl_module/`: existing EasyOCR preprocessing, extraction, normalization and matching pipeline.
- `frontend/src/`: React scan, watchlist, results/review interface and API client; `frontend/public/` holds route manifest, icon and provided sample label.
- `tests/`: deterministic parser/matcher/API tests, including a mocked OCR path; `sample_images/label.png` is the supplied end-to-end OCR fixture.
- `Dockerfile`, Python requirements and the frontend lockfile: reproducible production image with the FastAPI service and built UI on port 3000.

## Design

- **Design Movement:** Botanical Lab Notes, a tactile research notebook for people who read ingredient labels closely.
- **Core Principles:** Calm and legible; evidence before claims; gentle warnings with clear provenance; keep the scan and ingredient list in view.
- **Color Philosophy:** Warm paper and deep botanical ink make dense technical text approachable; terracotta is reserved for attention and watchlist alerts.
- **Layout Paradigm:** Editorial split workspace: a narrow scan rail beside a broad label/results column, then a flowing ingredient ledger rather than a generic dashboard grid.
- **Signature Elements:** Paper-like cards with quiet ruled dividers; small botanical-green index marks; terracotta match labels.
- **Interaction Philosophy:** Direct manipulation: preview before sending, edit recognized text before reparsing, remove watchlist entries in place, and explain every match as a name/synonym/family match.
- **Animation:** Brief scan-line sweep during OCR, subtle hover lift, and reduced-motion support; no movement that delays reading.
- **Typography System:** Lora for editorial headings and Manrope for interface labels and dense results; generous line-height for extracted text.
- **Brand Essence:** A clear-reading companion for cosmetic labels; careful, grounded, approachable.
- **Brand Voice:** Headlines are direct, never alarmist. Examples: “Read the small print with a little more confidence.” “We found a name from your watchlist.”
- **Wordmark & Logo:** A leaf-like INCI bracket mark paired with a compact wordmark; use a simple SVG mark.
- **Signature Brand Color:** Forest ink `#35483A`.

## Implementation constraints

EasyOCR uses pretrained detection/recognition weights and runs on CPU by default; the first analysis may take longer while weights initialize/download. OCR is best-effort, not a guarantee: surface uncertain text and let users correct it. Keep upload limits and supported image formats explicit. The managed database is shared with the published deployment; schema setup must be additive and idempotent. A browser ID is not authentication, so the UI must describe this as a browser-scoped workspace rather than a secure account. Do not store label images or imply medical safety.
