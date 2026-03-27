"""Retraction Watch checker — exact and fuzzy name matching."""

from typing import Optional, Dict, List
import pandas as pd
from rapidfuzz import fuzz, process


class RetractionChecker:
    """Check authors against an uploaded Retraction Watch CSV."""

    def __init__(self, df: pd.DataFrame, name_column: str):
        self.df = df
        self.name_column = name_column
        # Normalise for matching
        self.names_lower = (
            df[name_column]
            .dropna()
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )

    def check(self, author_name: str, threshold: int = 85) -> Dict:
        """
        Check a single author name.

        Returns:
            {"match": bool, "type": "exact"|"fuzzy"|None,
             "score": int, "matched_name": str|None}
        """
        needle = author_name.strip().lower()
        if not needle:
            return {"match": False, "type": None, "score": 0, "matched_name": None}

        # Exact match
        if needle in self.names_lower:
            return {"match": True, "type": "exact", "score": 100, "matched_name": needle}

        # Fuzzy match
        result = process.extractOne(
            needle, self.names_lower, scorer=fuzz.token_sort_ratio
        )
        if result and result[1] >= threshold:
            return {
                "match": True,
                "type": "fuzzy",
                "score": result[1],
                "matched_name": result[0],
            }

        return {"match": False, "type": None, "score": 0, "matched_name": None}

    def check_batch(
        self, author_names: List[str], threshold: int = 85
    ) -> Dict[str, Dict]:
        """Check a list of names. Returns {name: check_result}."""
        return {name: self.check(name, threshold) for name in author_names}
