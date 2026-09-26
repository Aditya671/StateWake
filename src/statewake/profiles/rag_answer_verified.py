"""Built-in rag_answer_verified reliability claim profile."""

from __future__ import annotations

from statewake.services.reliability_claim_profile_service import (
    get_builtin_claim_profile,
)

PROFILE_ID = "rag_answer_verified.v1"
PROFILE = get_builtin_claim_profile(PROFILE_ID)

__all__ = ["PROFILE", "PROFILE_ID"]
