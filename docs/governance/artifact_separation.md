# Artifact Separation

StateWake publishes three distinct archive roles:

1. **Production distribution** — the built wheel plus installation, license,
   security, third-party notice, changelog, and checksum information.
2. **Development support** — source, tests, verification scripts, CI definitions,
   project documentation, build configuration, and review evidence. These files
   support development and verification but are not installed as production
   runtime content.
3. **Complete source** — the full, purpose-renamed project used to create the
   other two archives.

The originally uploaded candidate is retained unchanged as a separate archival
artifact. It is not the renamed candidate and must not be mistaken for the
production distribution.

## Production inclusion rule

The production archive contains only:

- `statewake_ai-0.3.0-py3-none-any.whl`;
- `README.md`;
- `LICENSE`;
- `SECURITY.md`;
- `THIRD_PARTY_NOTICES.md`;
- `CHANGELOG.md`;
- `SHA256SUMS.txt`;
- `PRODUCTION_ARTIFACT.md`.

The wheel is the executable Python distribution. Repository tests, development
scripts, CI automation, release evidence, source history, and design documents
remain in the development-support and complete-source archives.

## Naming rule

Active files are named by purpose using lowercase `snake_case`. Historical
sequence identifiers such as `tier4` through `tier15` are not used in active
file, test-module, or verifier-module names. Historical narrative may still
refer to tiers where that wording describes the original architecture roadmap.

The complete mapping is recorded in `rename_map.tsv`.
