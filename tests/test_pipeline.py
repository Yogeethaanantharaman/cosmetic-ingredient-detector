from fastapi.testclient import TestClient

from backend import main
from dl_module.dl_service import _reconcile_names, parse_and_match
from dl_module.ingredient_extractor import extract_ingredients
from dl_module.ingredient_matcher import find_avoid_matches


def test_extracts_ordered_candidates_from_inci_heading():
    text = "INGREDIENTS / (INCI): Aqua (Water), Glycerin, Caprylic/Capric Triglyceride; Cetyl Alcohol\nDirections: Apply daily"
    assert extract_ingredients(text) == [
        "Aqua (Water)", "Glycerin", "Caprylic/Capric Triglyceride", "Cetyl Alcohol"
    ]


def test_ingredient_extraction_handles_empty_and_deduplicates():
    assert extract_ingredients("") == []
    assert extract_ingredients("Ingredients: Aqua, Glycerin, aqua") == ["Aqua", "Glycerin"]


def test_watchlist_alias_and_family_matches_attach_to_actual_detected_names():
    parsed = parse_and_match("Ingredients: Parfum, Methylparaben, Propylparaben, Watermelon extract", ["Fragrance", "Paraben", "water"])
    assert parsed["ingredients"] == ["Parfum", "Methylparaben", "Propylparaben", "Watermelon extract"]
    assert [(item["detected_ingredient"], item["ingredient"]) for item in parsed["matches"]] == [
        ("Parfum", "Fragrance"), ("Methylparaben", "Paraben"), ("Propylparaben", "Paraben")
    ]


def test_matching_does_not_flag_partial_words():
    assert find_avoid_matches("Watermelon extract", ["water"]) == []


def test_vision_filter_keeps_ocr_names_in_label_order_and_drops_unselected_copy():
    assert _reconcile_names(
        ["Aqua", "Sodium Benzoate", "Glycerin"],
        ["Aqua", "Nourished", "Glycerin", "Sodium Benzoate"],
    ) == ["Aqua", "Glycerin", "Sodium Benzoate"]


def test_upload_to_results_contract_with_mocked_ocr(monkeypatch):
    monkeypatch.setattr(main, "analyze_label", lambda _data, watchlist: {
        "extracted_text": "Ingredients: Aqua, Parfum",
        "ingredients": ["Aqua", "Parfum"],
        "matches": [{"ingredient": "Fragrance", "matched_term": "parfum", "detected_ingredient": "Parfum", "message": "Fragrance matched Parfum on the label."}],
        "detections": [{"text": "Aqua, Parfum", "confidence": 0.91}],
        "uncertain_text": [],
        "disclaimer": "Verify the original package.",
    })
    monkeypatch.setattr(main.db, "save_scan", lambda *args: None)
    monkeypatch.setattr(main.db, "is_ready", lambda: False)
    client = TestClient(main.app)
    response = client.post(
        "/api/analyze",
        headers={"X-Client-ID": "test-client"},
        data={"avoid_list": '["Fragrance"]', "product_name": "Test cream"},
        files={"file": ("label.png", b"\x89PNG\r\n\x1a\nvalid-by-mock", "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ingredients"] == ["Aqua", "Parfum"]
    assert data["matches"][0]["detected_ingredient"] == "Parfum"
    assert data["product_name"] == "Test cream"


def test_upload_rejects_malformed_image_before_ocr():
    client = TestClient(main.app)
    response = client.post(
        "/api/analyze",
        data={"avoid_list": "[]"},
        files={"file": ("bad.png", b"not a png", "image/png")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_image"


def test_review_endpoint_reparses_corrected_text_and_recomputes_matches():
    client = TestClient(main.app)
    response = client.post(
        "/api/review",
        headers={"X-Client-ID": "test-client"},
        json={"text": "Ingredients: Aqua, Parfum", "avoid_list": ["Fragrance"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ingredients"] == ["Aqua", "Parfum"]
    assert data["matches"][0]["detected_ingredient"] == "Parfum"
