# Contributing to Project Omni

Thank you for your interest in contributing to Project Omni! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Pull Request Guidelines](#pull-request-guidelines)

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Welcome contributors of all skill levels

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/project-omni.git
   cd project-omni
   ```
3. **Set up your development environment** (see below)

## Development Setup

### Quick Setup

Run the provided Makefile target:

```bash
make setup
```

This will:
- Create a virtual environment
- Install all dependencies (including dev dependencies)
- Install pre-commit hooks
- Install Playwright browsers

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-asyncio pytest-cov ruff mypy pre-commit

# Install pre-commit hooks
pre-commit install

# Install Playwright browsers
playwright install chromium
```

### Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

## Coding Standards

### Python Style

- **Formatting**: Code is automatically formatted using `ruff format`
- **Linting**: We use `ruff` for linting
- **Type Hints**: Use type hints for new code (gradually adding to existing code)
- **Line Length**: Maximum 100 characters

### Running Code Quality Checks

```bash
# Format code
make format

# Run linter
make lint

# Run type checker
make typecheck

# Run all pre-commit checks
make precommit
```

### Pre-commit Hooks

Pre-commit hooks are configured to run automatically before each commit. To run manually:

```bash
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_agent.py

# Run specific test function
pytest tests/test_agent.py::TestAgent::test_agent_creation
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Name test functions `test_*`
- Use `pytest` fixtures from `conftest.py`
- Mark async tests with `@pytest.mark.asyncio`

Example:

```python
import pytest

@pytest.mark.asyncio
async def test_example():
    result = await some_async_function()
    assert result == "expected"
```

## Submitting Changes

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the coding standards

3. **Write tests** for new functionality

4. **Run all checks**:
   ```bash
   make precommit
   make test
   ```

5. **Commit your changes**:
   - Use clear, descriptive commit messages
   - Reference issues when applicable
   - Sign off on commits: `git commit -s -m "Your message"`

6. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```

7. **Open a Pull Request** on GitHub

## Pull Request Guidelines

### PR Title

- Keep it concise and descriptive
- Use imperative mood: "Add feature" not "Added feature"
- Prefix with type when appropriate:
  - `feat:` New feature
  - `fix:` Bug fix
  - `docs:` Documentation changes
  - `refactor:` Code refactoring
  - `test:` Test additions/changes
  - `chore:` Maintenance tasks

### PR Description

Use the provided template and include:

- **Summary**: What changes does this PR make?
- **Motivation**: Why are these changes needed?
- **Testing**: How have you tested these changes?
- **Screenshots**: If applicable (for UI changes)

### Before Merging

Ensure your PR:
- [ ] Passes all CI checks (lint, typecheck, tests)
- [ ] Has been reviewed by at least one maintainer
- [ ] Includes tests for new functionality
- [ ] Updates documentation if needed
- [ ] Is rebased on the latest `main` branch

## Questions?

If you have questions or need help:

1. Check existing [issues](https://github.com/zhaojie/project-omni/issues)
2. Create a new issue with your question
3. Join discussions in existing issues

---

Thank you for contributing to Project Omni!
