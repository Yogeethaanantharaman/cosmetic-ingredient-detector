from dl_module.ingredient_extractor import extract_ingredients


SAMPLE_OCR = """NGREDIENTS / (INCI): Aqua (Water) Glycerin; Glycine Soja Oil, Capykchz
Triglyceride;
Cetyl
Alcohol;
Niacinamide;
Butyrospermum
Patii @
Ceteareth-20, Dimethicone, Citrus Limon Fruit Extract; Centella Asata"
Extract, Glycyrrhiza  Glabra
Root Extract;
Rosa Canina Frur
\"Tatt
Barbadensis Leaf Extract; Hydrolyzed Elastin, Prunus Avium Frui
Vesiculosus Extract; Sodium Polyacrylate, Betaine; Prunus Persk
Urea ,   Collagen;
Phenoxyethanol;
Propylene
Glycol,
Parfum;
Umonene , DMDM
Hydantoin;
Methylparaben,  Butylparaben;
Ropylparaben, Butylene Glycol, Diacetyl Boldine, Imidazolidinyl
Benzoate,
Sodium Citrate, Ethylhexylglycerin, Citric Acid.
( Eveline   Cosmetics
"""

EXPECTED = [
    "Aqua (Water)", "Glycerin", "Glycine Soja Oil", "Caprylic/Capric Triglyceride",
    "Cetyl Alcohol", "Niacinamide", "Butyrospermum Parkii Butter", "Ceteareth-20",
    "Dimethicone", "Citrus Limon Fruit Extract", "Centella Asiatica Leaf Extract",
    "Glycyrrhiza Glabra Root Extract", "Rosa Canina Fruit Extract", "Aloe Barbadensis Leaf Extract",
    "Hydrolyzed Elastin", "Prunus Avium Fruit Extract", "Fucus Vesiculosus Extract",
    "Sodium Polyacrylate", "Betaine", "Prunus Persica Fruit Extract", "Urea", "Collagen",
    "Phenoxyethanol", "Propylene Glycol", "Parfum", "Limonene", "DMDM Hydantoin",
    "Methylparaben", "Butylparaben", "Propylparaben", "Butylene Glycol", "Diacetyl Boldine",
    "Imidazolidinyl Urea", "Sodium Benzoate", "Sodium Citrate", "Ethylhexylglycerin", "Citric Acid",
]


def test_sample_ocr_repairs_all_ingredient_names_in_order_and_excludes_maker_text():
    assert extract_ingredients(SAMPLE_OCR) == EXPECTED


def test_promotional_copy_before_heading_is_not_returned_as_ingredients():
    text = (
        "Nourished, healthy & strong hair is now a reality! "
        "INGREDIENTS: Aqua, Glycerin, Panthenol"
    )
    assert extract_ingredients(text) == ["Aqua", "Glycerin", "Panthenol"]


def test_ocr_without_an_ingredient_heading_is_rejected():
    assert extract_ingredients("Nourished, healthy, strong hair, now a reality") == []
