# Security assurance decision and operational exception investigation

StateWake can inspect one explicitly configured `AssuranceDecision` JSON artifact and an optional `AssuranceException` JSON artifact without introducing a canonical decision-history store.

Configure the read API with:

```text
STATEWAKE_UI_ASSURANCE_DECISION=<decision JSON>
STATEWAKE_UI_ASSURANCE_EXCEPTION=<optional exception JSON>
```

The reader is GET-only, rejects symlink traversal, enforces hard byte limits, requires strict UTF-8 JSON objects, verifies deterministic record digests, and replays the existing assurance policy from the recorded decision inputs. A persisted decision whose digest is internally consistent but whose outcome/rule does not match `evaluate_assurance_decision()` is rejected.

New operational exceptions created by StateWake bind the exact decision digest. Historical exception records without `decision_digest` remain readable under their legacy digest contract and are presented as `legacy-unbound`; they are never represented as exact decision binding.

An operational exception is permitted only for `ALLOW_WITH_LIMITATIONS` and `REQUIRE_REVERIFICATION`. It never rewrites the underlying assurance state. The browser exposes privacy-safe identity digests instead of raw subject or authorizer identities and does not expose decision rationale.

The read surface does not establish factual correctness, publication permission, compliance certification, or broader host authorization.
