from pathlib import Path

from dl_module.dl_service import analyze_label


def test_supplied_label_runs_through_real_easyocr():
    image = Path(__file__).parents[1] / "sample_images" / "label.png"
    result = analyze_label(image.read_bytes(), ["Paraben", "Fragrance"])
    assert result["extracted_text"].strip()
    assert result["detections"]
    assert result["ingredients"]
    normalized = " ".join(result["ingredients"]).casefold()
    for expected in ("aqua", "glycerin", "niacinamide"):
        assert expected in normalized
    assert any(item["ingredient"] == "Paraben" for item in result["matches"])
