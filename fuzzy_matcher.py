"""
fuzzy_matcher.py
Fuzzy name matching for all entity types (SO, ASM, RSM, Beat, Outlet).
Uses rapidfuzz for tolerance against typos, abbreviations, and partial names.
"""

from rapidfuzz import process, fuzz
from typing import Optional


HIGH_CONFIDENCE = 90
MEDIUM_CONFIDENCE = 70


def _best_match(query: str, candidates: list[str]) -> tuple[str, float] | None:
    """Return (best_match_name, score) or None if no candidates."""
    if not candidates or not query:
        return None
    result = process.extractOne(
        query.strip(),
        candidates,
        scorer=fuzz.token_set_ratio,
        score_cutoff=0,
    )
    if result:
        return result[0], result[1]
    return None


def match_name(
    query: str,
    candidates: list[str],
    entity_type: str = "person",
) -> dict:
    """
    Match a query name against a list of candidate names.

    Returns a dict:
    {
        "status":      "matched" | "ambiguous" | "clarify" | "not_found",
        "matched":     str (the best match name) or None,
        "score":       float (0-100),
        "confidence":  "high" | "medium" | "low",
        "alternatives": list of (name, score) tuples for disambiguation,
        "message":     human-readable explanation (set for clarify/not_found),
    }
    """
    query = query.strip()
    if not query or not candidates:
        return {
            "status": "not_found",
            "matched": None,
            "score": 0,
            "confidence": "low",
            "alternatives": [],
            "message": f"No {entity_type} names available to match against.",
        }

    # Deduplicate candidates (case-insensitive)
    unique_candidates = list({c.strip() for c in candidates if c and str(c).strip()})

    # Get top-5 matches
    top_matches = process.extract(
        query,
        unique_candidates,
        scorer=fuzz.token_set_ratio,
        limit=5,
        score_cutoff=0,
    )

    if not top_matches:
        return {
            "status": "not_found",
            "matched": None,
            "score": 0,
            "confidence": "low",
            "alternatives": [],
            "message": f"I couldn't find any {entity_type} matching '{query}'.",
        }

    best_name, best_score, _ = top_matches[0]

    # Collect all matches within 5 points of the best score to detect ambiguity
    near_top = [
        (name, score)
        for name, score, _ in top_matches
        if score >= best_score - 5 and score >= MEDIUM_CONFIDENCE
    ]

    # Ambiguity: multiple names are equally close
    if len(near_top) > 1 and best_score >= MEDIUM_CONFIDENCE:
        alternatives_str = "\n".join(
            f"  • {name}" for name, _ in near_top[:5]
        )
        return {
            "status": "ambiguous",
            "matched": None,
            "score": best_score,
            "confidence": "medium",
            "alternatives": near_top,
            "message": (
                f"I found multiple {entity_type}s matching '{query}'. "
                f"Did you mean one of these?\n{alternatives_str}"
            ),
        }

    if best_score >= HIGH_CONFIDENCE:
        return {
            "status": "matched",
            "matched": best_name,
            "score": best_score,
            "confidence": "high",
            "alternatives": [],
            "message": None,
        }

    if best_score >= MEDIUM_CONFIDENCE:
        return {
            "status": "clarify",
            "matched": best_name,
            "score": best_score,
            "confidence": "medium",
            "alternatives": [(best_name, best_score)],
            "message": f"Did you mean **{best_name}**?",
        }

    # Low confidence — suggest top-3
    top3 = [(name, score) for name, score, _ in top_matches[:3]]
    suggestions = ", ".join(f"**{name}**" for name, _ in top3)
    return {
        "status": "not_found",
        "matched": None,
        "score": best_score,
        "confidence": "low",
        "alternatives": top3,
        "message": (
            f"I couldn't find a {entity_type} called '{query}'. "
            f"Did you mean one of these: {suggestions}?"
        ),
    }


def resolve_name_in_context(
    query: str,
    candidates: list[str],
    entity_type: str,
    extra_info: dict | None = None,
) -> dict:
    """
    Convenience wrapper that returns match result enriched with entity_type.
    extra_info can be {name: "ASM: South Region"} etc. for disambiguation display.
    """
    result = match_name(query, candidates, entity_type)
    result["entity_type"] = entity_type
    result["query"] = query

    if extra_info and result["status"] == "ambiguous":
        # Enrich alternatives with context strings
        enriched = []
        for name, score in result["alternatives"]:
            context = extra_info.get(name, "")
            label = f"{name} ({context})" if context else name
            enriched.append((label, score))
        result["alternatives"] = enriched
        alternatives_str = "\n".join(f"  • {label}" for label, _ in enriched[:5])
        result["message"] = (
            f"I found multiple {entity_type}s matching '{query}'. "
            f"Which one did you mean?\n{alternatives_str}"
        )

    return result
