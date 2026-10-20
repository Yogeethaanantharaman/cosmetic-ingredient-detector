
import re

STOP_MARKERS = [
    r"WHAT\s*['’$]?\s*S?\s+OUT",
    r"PARABENS",
    r"PHTHALATES",
    r"NO SYNTHETIC FRAGRANCES",
    r"ANIMAL.DERIVED",
    r"100%\s*VEGAN",
]

def extract_ocr_ingredients(text):
    if not text or not text.strip():
        return []

    text = re.sub(r"\s+", " ", text).strip()

    # Accept standard ingredient headings.
    heading = re.search(
        r"\bINGREDIENTS?\b\s*[:;.\-]?",
        text,
        re.IGNORECASE,
    )

    if heading:
        text = text[heading.end():]

    else:
        # Recovery for damaged headings:
        # Only start at a clearly recognizable ingredient anchor.
        anchor = re.search(
            r"\b(?:Aqua|Water)\s*[,;]",
            text,
            re.IGNORECASE,
        )

        if not anchor:
            return []

        text = text[anchor.start():]

    # Stop before non-ingredient marketing claims.
    for pattern in STOP_MARKERS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = text[:match.start()]

    # Recover some common OCR separator errors.
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+", " ", text)

    # Split on commas and semicolons, keeping parentheses.
    candidates = re.split(r"[,;]+", text)

    ingredients = []
    seen = set()

    for candidate in candidates:
        name = candidate.strip(" \t\n.*:-")

        if not name:
            continue

        if len(name) > 100:
            continue

        if not re.search(r"[A-Za-z]", name):
            continue

        # Reject obvious marketing text.
        if re.search(
            r"\b(?:vegan|formulation|fragrances|"
            r"animal-derived|colour variation|"
            r"tested|parabens)\b",
            name,
            re.IGNORECASE,
        ):
            continue

        key = name.casefold()

        if key not in seen:
            ingredients.append(name)
            seen.add(key)

    return ingredients


if __name__ == "__main__":
    sample = (
        "WHAT S IN AgRFDOpaned Aqua, "
        "Oryza Sativa (Black Rice) Extract; "
        "Niacinamide; Propanediol, Lysine, "
        "Histidine; Arginine; Glutamic Acid, "
        "Aspartic Acid, Threonine, Serine, "
        "Proline; Glycine, Alanine; Valine; "
        "Methionine, Isoleucine; Leucine; "
        "Tyrosine; Phenylalanine, Xylitol, "
        "Sodium Polyglutamate Crosspolymer; "
        "Alpha-Arbutin, Disodium EDTA "
        "WHAT'S OUT Parabens"
    )

    results = extract_ocr_ingredients(sample)

    print("Total candidates:", len(results))

    for i, ingredient in enumerate(results, 1):
        print(f"{i}. {ingredient}")
