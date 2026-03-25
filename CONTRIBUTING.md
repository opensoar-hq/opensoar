# Contributing to OpenSOAR

Thanks for your interest in contributing to OpenSOAR! This guide will help you get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/opensoar-hq/opensoar-core.git
cd opensoar-core

# Create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start dependencies
docker compose up -d postgres redis

# Run tests
pytest tests/ -v --tb=short
```

## Development Workflow (TDD)

We follow test-driven development:

1. **Write tests first** — define expected behavior before implementation
2. **Run tests** — confirm they fail for the right reasons
3. **Implement** — write the minimal code to make tests pass
4. **Lint** — `ruff check src/ tests/` must pass with zero errors
5. **Run full suite** — `pytest tests/ -v --tb=short`
6. **Commit** — tests + implementation together

## What to Contribute

- **Integrations** — SIEM normalizers, enrichment APIs, response tool connectors
- **Playbooks** — community playbook packs for common IR scenarios
- **Frontend** — dashboard improvements, new visualizations, UX enhancements
- **Documentation** — guides, tutorials, deployment recipes
- **Bug fixes** — check the issue tracker for open bugs

## Pull Request Process

1. Fork the repo and create a feature branch from `main`
2. Write tests for your changes
3. Ensure all tests pass and linting is clean
4. Keep PRs focused — one feature or fix per PR
5. Write a clear PR description explaining what and why

## Code Style

- **Python**: We use `ruff` for linting. Run `ruff check src/ tests/` before committing.
- **TypeScript**: The UI uses React 19 + TypeScript + Tailwind CSS v4. Run `tsc -b` to check types.
- **Commits**: Use clear, concise commit messages. One logical change per commit.

## Architecture Notes

- All DB operations are async (`AsyncSession`)
- Playbooks use `@playbook` and `@action` decorators
- API endpoints are FastAPI with Pydantic v2 schemas
- The plugin system loads optional enterprise features — keep core features in the open-source package

## Reporting Issues

- Use GitHub Issues for bugs and feature requests
- Include reproduction steps for bugs
- Check existing issues before creating duplicates

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
