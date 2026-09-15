# Troubleshooting

## `ModuleNotFoundError: statewake`

Install the distribution into the environment that runs the application:

```bash
python -m pip install statewake-ai
```

Then verify:

```bash
python -c "import statewake; print(statewake.__version__)"
```

## Verification reports a digest mismatch

Treat this as an integrity failure. Check whether the source artifact changed after the evidence receipt, chain, or proof was created. Do not overwrite the evidence record to make the digest match.

## HTTP verification cannot read a path

The WSGI adapter verifies local paths. Confirm that the StateWake process can read the supplied path and that the path is inside the application's intended trust boundary.

## Signed verification reports a missing PyNaCl package

Signed Ed25519 verification is included in the package dependency set and is available after the normal `statewake-ai` installation.

## CLI command is missing

Run:

```bash
statewake --help
```

The CLI intentionally exposes only the active StateWake product boundary. Historical commands retained in the `repository history` historical archive are not part of the supported interface.
