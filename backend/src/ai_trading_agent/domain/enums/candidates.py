"""Enumerations for transparent market-candidate ranking."""

from enum import StrEnum


class CandidateRanking(StrEnum):
    """Research-only ranking lenses exposed by the candidate pool."""

    COMPOSITE = "composite"
    MOMENTUM = "momentum"
    BALANCED_ENTRY = "balanced_entry"
