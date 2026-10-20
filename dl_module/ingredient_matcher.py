
import re
from typing import Any


# Common alternative names used on cosmetic labels.
SYNONYMS = {
    "fragrance": ["parfum", "perfume"],
    "parfum": ["fragrance", "perfume"],
    "perfume": ["fragrance", "parfum"],
}


# Ingredients belonging to the paraben family.
INGREDIENT_FAMILIES = {
    "paraben": [
        "methylparaben",
        "ethylparaben",
        "propylparaben",
        "butylparaben",
        "isopropylparaben",
        "isobutylparaben",
        "benzylparaben",
    ],
}


# Specific OCR variants observed during our image testing.
# These are explicit corrections, not general fuzzy matching.
OCR_VARIANTS = {
    "phenoxyethanol": [
        "phenoxyed ol",
    ],
}


def normalize_text(text: str) -> str:
    """Normalize text for case-insensitive ingredient matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_term(text: str, term: str) -> bool:
    """Match a complete word or phrase, not a partial word."""
    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)

    if not normalized_term:
        return False

    pattern = rf"\b{re.escape(normalized_term)}\b"
    return bool(re.search(pattern, normalized_text))


def find_avoid_matches(
    extracted_text: str,
    avoid_list: list[str]
) -> list[dict[str, Any]]:
    """Find avoid-list ingredients in extracted label text."""
    matches = []
    already_matched = set()

    for ingredient in avoid_list:
        ingredient = ingredient.strip()

        if not ingredient:
            continue

        normalized_ingredient = normalize_text(ingredient)

        search_terms = [ingredient]

        # Add known synonyms.
        search_terms.extend(
            SYNONYMS.get(normalized_ingredient, [])
        )

        # Add ingredient-family members.
        search_terms.extend(
            INGREDIENT_FAMILIES.get(normalized_ingredient, [])
        )

        # Add only explicitly tested OCR variants.
        search_terms.extend(
            OCR_VARIANTS.get(normalized_ingredient, [])
        )

        for term in search_terms:
            if contains_term(extracted_text, term):
                key = normalized_ingredient

                if key not in already_matched:
                    matches.append({
                        "ingredient": ingredient,
                        "matched_term": term,
                        "message": (
                            f"'{ingredient}' matched the label text "
                            f"as '{term}'."
                        )
                    })
                    already_matched.add(key)

                break

    return matches
