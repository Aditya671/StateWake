# Contributing to StateWake

Thank you for contributing to StateWake. StateWake is reliability infrastructure: changes should preserve verifiability, provenance, deterministic behavior, and a clear separation between the reliability core and external integration surfaces.

## Development setup

StateWake supports Python 3.11–3.13.

```bash
uv sync
uv run pytest
uv run python -m unittest discover -s tests -p 'test_*.py'
```

## Before opening a pull request

Run the complete local verification set:

```bash
uv run python scripts/release/verify_versioning.py
python -m compileall -q src tests scripts
uv run pytest
uv run python -m unittest discover -s tests -p 'test_*.py'
uv build
```

Also check that active source does not import from `legacy/` and that all Python modules parse successfully.

## Engineering principles

1. **Preserve the StateWake boundary.** StateWake establishes verifiable reliability evidence and trustworthy system state; it is not an orchestration or generic testing platform.
2. **Prefer existing authoritative evidence.** Do not duplicate data that an integrated producer already owns when a verifiable reference can be used.
3. **Deterministic first.** Use ordinary software for deterministic requirements; introduce model-dependent behavior only where it is actually necessary.
4. **Keep the public API small.** New public symbols require an explicit integration rationale and tests.
5. **Keep adapters at the boundary.** Framework, storage, transport, and host integrations belong behind adapters.
6. **Make failures explainable.** Verification failures should identify the broken invariant or evidence relationship.
7. **Test the complete lifecycle.** Changes affecting evidence, state, reconciliation, or attestation require regression coverage across the affected chain.

## Documentation

User-facing documentation belongs under `docs/user-guide/`. Engineering design records belong in the categorized `docs/` sections, and architecture decisions belong under `docs/adr/`.

## Commit and pull-request guidance

Prefer small, behavior-oriented commits. Pull requests should explain:

- the problem being solved;
- the StateWake architectural boundary involved;
- compatibility implications;
- verification performed; and
- documentation changes.

Do not describe historical phase numbers as future work unless the architecture audit explicitly authorizes them.

## Code of conduct

Participation is subject to [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Security issues

Do not report security vulnerabilities through public issues. Follow [`SECURITY.md`](SECURITY.md).
