# INCI Sight

INCI Sight scans cosmetic ingredient labels using the supplied EasyOCR pipeline, parses an ordered list of ingredient candidates, and checks each candidate against a user's personal watchlist. It shows the recognized source text and lower-confidence OCR detections, and lets the user correct the OCR text and rerun parsing.

## Run locally

Install the pinned Python packages with `pip install -r requirements.txt`. Install frontend packages with `cd frontend && npm ci && npm run build`. Start the combined app from the project root with `uvicorn backend.main:app --host 0.0.0.0 --port 3000`. Then open `http://localhost:3000`; `GET /health` reports backend readiness. The first real scan may download EasyOCR's pretrained weights and take longer than later scans.

The included sample is `/sample-label.png` or `sample_images/label.png`. In the UI choose **Try the provided sample label** to run it through the same upload/OCR/matching path as a user photo.

## Persistence and privacy

When `DATABASE_URL` is available, the backend creates additive `inci_watchlists` and `inci_scans` tables and stores watchlist terms and scan text/results per browser UUID. Without the managed MySQL connection, the app continues to scan and uses browser local storage for its watchlist and recent history. A browser UUID is not authentication or a secure user account. Uploaded image bytes are processed for the request and are not stored; scan history contains text and parsed ingredient names only.

## Checks

Run deterministic tests with `python -m pytest -q tests/test_pipeline.py`. They cover ingredient extraction, exact/alias/family matching, scan response shape and upload validation. `python -m pytest -q tests/test_real_sample.py` is the EasyOCR sample-image integration check and loads pretrained weights.

## Limits

OCR can misread small, curved, reflective, multilingual or blurred print. Ingredient extraction is a text parser, not an ingredient database; it does not infer safety, functions or medical risk. Verify names against the package. A missing match does not guarantee safety.
