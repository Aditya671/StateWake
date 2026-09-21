"""Built-in ai_decision_with_limitations reliability claim profile."""

from __future__ import annotations

from statewake.services.reliability_claim_profile_service import (
    get_builtin_claim_profile,
)

PROFILE_ID = "ai_decision_with_limitations.v1"
PROFILE = get_builtin_claim_profile(PROFILE_ID)

__all__ = ["PROFILE", "PROFILE_ID"]
