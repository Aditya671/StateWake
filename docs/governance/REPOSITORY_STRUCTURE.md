# Repository Structure

StateWake follows a small, purpose-based repository layout. The repository contains active product source, tests, release automation, and documentation required to build, verify, and operate the package. Generated runtime data, build output, and historical engineering artifacts are kept outside the source tree.

```text
StateWake/
├── .github/                 # CI/CD, issue templates, repository automation
├── config/                  # canonical repository path configuration
├── docs/
│   ├── user-guide/          # public product documentation
│   ├── reference/           # API/SDK contracts
│   ├── architecture/       # active system architecture and boundaries
│   ├── specifications/     # versioned domain specifications
│   ├── development/        # developer workflow and tooling
│   ├── testing/            # validation strategy and evidence
│   ├── security/           # security model and controls
│   ├── operations/         # operational state and recovery
│   ├── governance/         # project, repository, and release governance
│   ├── integrations/       # external integration documentation
│   ├── examples/            # executable examples and reference applications
│   └── adr/                 # accepted architecture decisions
├── scripts/
│   ├── common/              # shared validation helpers and types
│   ├── development/        # developer verification utilities
│   ├── testing/             # validation and adversarial campaigns
│   ├── integration/         # external integration runners
│   └── release/             # release and package verification gates
├── src/statewake/           # active Python package
├── tests/                   # active automated test suite and fixtures
├── pyproject.toml           # package and tool configuration
├── uv.lock                 # dependency lockfile
└── README.md                # project entry point
```

The source tree is the only runtime implementation authority. Build artifacts, local databases, temporary validation output, and superseded engineering records are not committed to the active repository baseline.
