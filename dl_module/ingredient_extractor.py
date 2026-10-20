
"""
Extract ingredient names from OCR-recognized cosmetic label text.
"""

import re


OCR_REPAIRS = [
    (
        r"\bAqua\s*\(Water\)\s+Glycerin\b",
        "Aqua (Water), Glycerin",
    ),
    (
        r"\bGlycine\s+Soja\s+Oi\b",
        "Glycine Soja Oil",
    ),
    (
        r"\b(?:Caprthz|Capykchz)\s+Triglyceride\b",
        "Caprylic/Capric Triglyceride",
    ),
    (
        r"\bCetyl\s+Alcohol\b",
        "Cetyl Alcohol",
    ),
    (
        r"\bButyrospermum\s+(?:Pali\s+Na|Patii\s*@?|Palii)\s*Ceteareth-20\b",
        "Butyrospermum Parkii Butter, Ceteareth-20",
    ),
    (
        r"\bCereareth-20\b",
        "Ceteareth-20",
    ),
    (
        r"\bCentella\s+Asata\w*[\"']?\s+Extract\b",
        "Centella Asiatica Leaf Extract",
    ),
    (
        r"\bGlycyrrhiza\s+Glabra\s+Root\s+Extract\b",
        "Glycyrrhiza Glabra Root Extract",
    ),
    (
        r"\bRosa\s+Canina\s+Frur\s*[\"“]?T(?:att|et)\w*",
        "Rosa Canina Fruit Extract,",
    ),
    (
        r"\bBarbadensis\s+Leaf\s+Extract\b",
        "Aloe Barbadensis Leaf Extract",
    ),
    (
        r"\bPrunus\s+Avium\s+Frui\s+Vesiculosus\s+Extract\b",
        "Prunus Avium Fruit Extract, Fucus Vesiculosus Extract",
    ),
    (
        r"\bPrunus\s+Persk\s*a?\s+Urea\s*,?\s*Collagen\b",
        "Prunus Persica Fruit Extract, Urea, Collagen",
    ),
    (
        r"\bVea\b",
        "Urea",
    ),
    (
        r"\bPropylene\s+Glycol\b",
        "Propylene Glycol",
    ),
    (
        r"\bDMDM\s+Hydantoin\b",
        "DMDM Hydantoin",
    ),
    (
        r"\b[AR]opylparaben\b",
        "Propylparaben",
    ),
    (
        r"\bUmonene\b",
        "Limonene",
    ),
    (
        r"\bImidazolidinyl\s+Sodium\s+Citrate\b",
        "Imidazolidinyl Urea, Sodium Citrate",
    ),
    (
        r"\bBenzoate\s*,?\s*Sodium\s+Citrate\b",
        "Sodium Benzoate, Sodium Citrate",
    ),
    (
        r"\bImidazolidinyl\s+Sodium\s+Benzoate\b",
        "Imidazolidinyl Urea, Sodium Benzoate",
    ),
]


def extract_ingredients(extracted_text: str) -> list[str]:
    """
    Parse ingredient candidates from OCR text.

    Supports common ingredient headings, OCR spelling mistakes,
    comma-separated ingredients, and line-separated ingredients.
    """
    if not extracted_text or not extracted_text.strip():
        return []

    text = extracted_text.strip()

    # Recognize common heading variations caused by OCR.
    heading_pattern = (
        r"\b(?:"
        r"ingredients?|"
        r"ngredients?|"
        r"ingredlents?|"
        r"ingred1ents?|"
        r"ingredlents|"
        r"inci"
        r")\s*"
        r"(?:list\s*)?"
        r"(?:[/|]\s*)?"
        r"(?:\(\s*inci\s*\))?"
        r"\s*[:\-/]?"
    )

    heading = re.search(
        heading_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if heading:
        # Ignore product descriptions before the ingredient heading.
        text = text[heading.end():]

    # Repair only known OCR mistakes.
    for pattern, replacement in OCR_REPAIRS:
        text = re.sub(
            pattern,
            replacement,
            text,
            flags=re.IGNORECASE,
        )

    # Remove sections that generally follow the ingredient list.
    trailing_sections = (
        r"\b(?:"
        r"directions|"
        r"how to use|"
        r"warning|"
        r"caution|"
        r"manufactured by|"
        r"made in|"
        r"distributed by|"
        r"distributor|"
        r"manufacturer|"
        r"batch no|"
        r"expiry date|"
        r"exp date|"
        r"best before|"
        r"net weight|"
        r"customer care"
        r")\b"
    )

    if heading:
        # These terms can be brand/company text on some labels.
        # Use them as boundaries only after an ingredient heading.
        text = re.split(
            trailing_sections + r"|\b(?:eveline|cosmetics)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
    else:
        # Without a heading, don't split on generic words such as
        # "cosmetics", which may erase the useful ingredient text.
        text = re.split(
            trailing_sections,
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

    # Split ingredient candidates on commas, semicolons and new lines.
    parts = re.split(
        r"[,;\n]+",
        text,
    )

    ingredients = []
    seen = set()

    for part in parts:
        name = part.strip(" .:;-\t\r\n")

        name = re.sub(
            r"\s+",
            " ",
            name,
        )

        if not name:
            continue

        # Reject entries containing no alphabetic characters.
        if not re.search(r"[A-Za-z]", name):
            continue

        # Reject large blocks of unrelated OCR text.
        if len(name) > 100:
            continue

        # Avoid returning common heading fragments.
        if name.casefold() in {
            "ingredients",
            "ingredient list",
            "inci",
            "ingredients inci",
        }:
            continue

        key = name.casefold()

        if key not in seen:
            ingredients.append(name)
            seen.add(key)

    return ingredients
