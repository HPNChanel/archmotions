# Contributing to ArchMotion 🎬

Thank you for your interest in contributing! This guide will help you get started.

## 🚀 Quick Setup (Development)

```bash
# Clone repository
git clone https://github.com/archmotion/archmotion.git
cd archmotion

# Create virtual environment (recommended: uv)
uv venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install with dev dependencies
uv pip install -e ".[dev]"

# Verify setup
pytest tests/ -v
ruff check src/
mypy src/archmotion --strict
```

## 📝 Code Style

| Tool | Purpose | Command |
|---|---|---|
| **Ruff** | Linting + Formatting | `ruff check src/` / `ruff format src/` |
| **mypy** | Static type checking | `mypy src/archmotion --strict` |
| **pytest** | Testing | `pytest tests/ -v --cov=archmotion` |

- **Docstrings**: Google style
- **Naming**: PEP 8 (`snake_case` for functions/variables, `PascalCase` for classes)
- **Type Hints**: Mandatory on all public APIs. `mypy --strict` must pass.
- **Line Length**: 100 characters max

## 🏛️ Architecture Rules

Before writing code, **read `CORE_ENGINE&ARCHITECTURE.md`** to understand the 4-Phase Pipeline.

| Rule | Description |
|---|---|
| **Phase Isolation** | Do NOT mix logic between Phases. Each Phase has clear Input/Output types |
| **Skia Containment** | Only `src/archmotion/renderer/` may `import skia` |
| **Subprocess Containment** | Only `src/archmotion/exporter/` may `import subprocess` |
| **Zero-Disk** | NEVER write intermediate frame images to disk |
| **Type Safety** | `mypy --strict` must pass. No `# type: ignore` without justification |

## 🔀 Pull Request Process

1. **Fork** the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Write code following the style guide above
4. Add/update tests (target: 80%+ coverage)
5. Commit using [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add new easing function`
   - `fix: resolve memory leak in Skia canvas cleanup`
   - `docs: update API reference for Transfer animation`
   - `refactor: simplify timeline compiler`
   - `perf: optimize frame serialization with SharedMemory`
6. Ensure CI passes: `pytest`, `ruff check`, `mypy --strict`
7. Open a PR with a clear description
8. Wait for review from a maintainer

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=archmotion --cov-report=html

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests (requires FFmpeg)
pytest tests/integration/ -v -m integration

# Skip slow tests
pytest tests/ -v -m "not slow"
```

## 📦 Release Process

Releases are automated via GitHub Actions when a version tag is pushed.
Only maintainers can create releases. See `CHANGELOG.md` for the format.

## 💬 Getting Help

- **Questions**: Open a [Discussion](https://github.com/archmotion/archmotion/discussions)
- **Bugs**: File an [Issue](https://github.com/archmotion/archmotion/issues/new?template=bug_report.yml)
- **Features**: File a [Feature Request](https://github.com/archmotion/archmotion/issues/new?template=feature_request.yml)
