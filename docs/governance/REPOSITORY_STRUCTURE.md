# Repository Structure

StateWake uses a purpose-based `src/` repository layout. Active product source, tests, executable examples, release automation, UI source, benchmark fixtures, and human documentation each have one predictable home. Generated runtime data, build output, caches, and superseded engineering artifacts are not implementation authorities.

```text
StateWake/
├── .github/                 # CI/CD, issue templates, repository automation
├── benchmarks/              # bounded validation fixtures and frozen reference results
├── data/                    # documented local runtime-data boundary; generated content ignored
├── docs/
│   ├── user-guide/          # public product documentation
│   ├── releases/            # source-controlled release history and evidence boundaries
│   ├── reference/           # API/SDK contracts
│   ├── architecture/        # active system architecture and boundaries
│   ├── specifications/      # versioned domain specifications
│   ├── development/         # developer workflow and tooling
│   ├── testing/             # validation strategy and evidence guidance
│   ├── security/            # security model and controls
│   ├── operations/          # workspace, deployment, backup, migration, recovery
│   ├── governance/          # project, repository, and release governance
│   ├── integrations/        # external integration documentation
│   ├── research/            # bounded research narrative
│   ├── release/             # release-trust documentation
│   ├── whitepaper/          # published white paper and grounding material
│   └── adr/                 # accepted architecture decisions
├── examples/                # executable public examples and reference applications
├── scripts/
│   ├── common/              # shared repository/release helpers and canonical paths
│   ├── development/         # developer verification utilities
│   ├── testing/             # validation and adversarial campaigns
│   ├── integration/         # external integration runners
│   ├── security/            # security-assurance verifiers
│   └── release/             # release and package verification gates
├── src/statewake/           # only production Python implementation authority
├── tests/                   # active automated test suite and fixtures
├── ui/                      # optional Next.js inspection/review UI
├── pyproject.toml           # package and Python tool configuration
├── uv.lock                  # reproducible Python dependency lockfile
└── README.md                # repository/product entry point
```

## Placement rules

- Production Python implementation belongs only under `src/statewake/`.
- Runnable examples belong under `examples/`; documentation may link to them but does not act as a Python package.
- Repository-only Python helpers belong under categorized `scripts/`, not in a pseudo-runtime `config` package.
- Human-readable configuration templates may use a future `config/` directory if StateWake gains real configuration files; executable helpers do not.
- Generated runtime data belongs below an ignored runtime location such as `data/statewake/` or an operator-supplied workspace path.
- Generated build output, caches, local evidence, and validation scratch data are disposable and excluded from release identity.
- Historical release records retain the names and paths that were true for those releases; active files use purpose-based names rather than development sequence labels.

The source tree and its maintained release-input selector remain the implementation/release authorities. Structure changes must update references, tests, release scope, and generated identity manifests together.
