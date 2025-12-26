from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class TrainSummary:
    code: str


def prioritize_favorites(favorites: Iterable[str], candidates: Iterable[str]) -> List[str]:
    """Return train codes with favorites promoted while preserving relative order."""
    favorite_order = list(dict.fromkeys(favorites))
    candidate_list = list(candidates)
    favorites_in_results = [code for code in favorite_order if code in candidate_list]
    remaining = [code for code in candidate_list if code not in favorite_order]
    return favorites_in_results + remaining
