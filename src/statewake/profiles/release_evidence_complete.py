"""Built-in release_evidence_complete reliability claim profile."""

from __future__ import annotations

from statewake.services.reliability_claim_profile_service import (
    get_builtin_claim_profile,
)

PROFILE_ID = "release_evidence_complete.v1"
PROFILE = get_builtin_claim_profile(PROFILE_ID)

__all__ = ["PROFILE", "PROFILE_ID"]
