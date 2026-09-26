# NLTK transitive advisory review

**Review date:** 2026-09-25  
**Advisory:** [CVE-2026-81726 / GHSA-8mgp-746c-j5xp](https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp)  
**Status:** StateWake code-path review complete; dependency finding remains open; no risk acceptance recorded.

## Dependency path

`nltk==3.10.3` is present in `uv.lock` as a transitive dependency of
`llama-index-core`. StateWake does not declare NLTK directly.

## StateWake code-path review

A source search of `src/`, `tests/`, and `scripts/` found no NLTK imports or
calls to the affected model-artifact APIs (`TransitionParser.train/parse`,
`AveragedPerceptron.save/load`, `PerceptronTagger.save_to_json`, or
`save_maxent_params`). StateWake's native LlamaIndex adapter consumes
instrumentation events and observed retrieval data; its public configuration
does not accept NLTK model-file paths or invoke NLTK model persistence/loading.

The advisory's stated precondition is an application enabling NLTK `pathsec`
and allowing untrusted workflows to choose model import/export paths. No such
path is exposed by the reviewed StateWake adapter. This is evidence that the
reviewed StateWake integration path does not itself reach the vulnerable sinks;
it is not proof that every application installing StateWake is safe. NLTK
remains installed, so host code or another dependency could call the affected
APIs directly.

## Required handling

- Do not pass attacker-controlled paths to NLTK model-artifact APIs. Where an
  application uses NLTK with untrusted workflows, isolate that work and enforce
  path restrictions at the application boundary; do not rely on NLTK `pathsec`
  alone for the affected APIs.
- Keep the dependency audit finding visible. As of this review, the upstream
  advisory lists no patched release. Do not label the package clean or suppress
  the finding based only on this StateWake call-path review.
- Recheck the advisory and lock to a published patched NLTK release when one is
  available, then rerun `pip-audit`, the supported Python test matrix, and the
  release verification gates.
- Until then, release use requires explicit risk acceptance by the security or
  release owner. This document records technical scope only; it does not grant
  that acceptance.

## Evidence and limitations

- `uv.lock`: NLTK 3.10.3 is required by `llama-index-core`.
- `src/statewake/integrations/native_llamaindex.py`: reviewed adapter boundary;
  no NLTK dependency API or model path is used.
- `rg -n -i '\bnltk\b|nltk\.' src tests scripts pyproject.toml`: no direct
  NLTK references in StateWake source, tests, scripts, or declared dependencies.
- The upstream advisory describes the affected APIs and currently lists no
  patched version. Recheck before each release because this status can change.
