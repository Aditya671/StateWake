# FAQ

## Is StateWake an agent framework?

No. StateWake integrates with agent runtimes and focuses on reliability evidence and trustworthy state.

## Does StateWake replace observability?

No. Observability systems remain useful evidence producers. StateWake provides a verifiable reliability layer around authoritative evidence.

## Does StateWake require an LLM?

No. The core package has no required model dependency and prioritizes deterministic verification.

## Can I use StateWake from another Python project?

Yes. Install `statewake-ai` and import the stable public API from `statewake`.

## Can I call StateWake over HTTP?

Yes. The package includes a standard-library WSGI adapter. It is intended to be hosted behind a trusted application/security boundary.

## Is StateWake a hosted service?

The package release is not a hosted SaaS service. Hosting, authentication, tenancy, and network security are deployment concerns outside the reliability core.

## Why is the distribution named `statewake-ai` but imported as `statewake`?

`statewake-ai` is the PyPI distribution identifier; `statewake` is the Python import namespace. This follows normal Python packaging conventions where a distribution name and import package name can differ.
