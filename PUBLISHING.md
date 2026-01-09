# Publishing to PyPI

## Prerequisites

1. Install build tools:
```bash
pip install build twine
```

2. Create PyPI account at https://pypi.org/account/register/

3. Generate API token at https://pypi.org/manage/account/token/

## Build Package

```bash
python -m build
```

This creates:
- `dist/mcp_task_rmq_queue-0.1.0.tar.gz` (source distribution)
- `dist/mcp_task_rmq_queue-0.1.0-py3-none-any.whl` (wheel)

## Test Upload (TestPyPI)

```bash
twine upload --repository testpypi dist/*
```

Test installation:
```bash
pip install --index-url https://test.pypi.org/simple/ mcp-task-rmq-queue
```

## Production Upload

```bash
twine upload dist/*
```

## Automated Publishing

The package includes GitHub Actions workflow that automatically publishes to PyPI when you create a release:

1. Update version in `pyproject.toml` and `src/__init__.py`
2. Commit and push changes
3. Create a new release on GitHub
4. GitHub Actions will build and publish automatically

### Setup GitHub Secrets

Add `PYPI_API_TOKEN` to your repository secrets:
1. Go to repository Settings > Secrets and variables > Actions
2. Add new secret named `PYPI_API_TOKEN`
3. Paste your PyPI API token

## Version Bumping

Update version in two places:
- `pyproject.toml`: `version = "0.1.1"`
- `src/__init__.py`: `__version__ = "0.1.1"`
