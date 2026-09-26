"""Built-in human_approval_recorded reliability claim profile."""

from __future__ import annotations

from statewake.services.reliability_claim_profile_service import (
    get_builtin_claim_profile,
)

PROFILE_ID = "human_approval_recorded.v1"
PROFILE = get_builtin_claim_profile(PROFILE_ID)

__all__ = ["PROFILE", "PROFILE_ID"]
