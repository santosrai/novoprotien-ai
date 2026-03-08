# Playwright Testing Framework

A comprehensive Playwright testing framework for NovoProtein AI, inspired by TestSprite architecture.

## Overview

This testing framework provides:
- Organized folder structure by test category
- Configuration management for environments and test settings
- Reusable page objects and base test classes
- Comprehensive test documentation
- Automated test execution and reporting
- Standardized naming conventions

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install playwright
   playwright install chromium
   ```

2. **Start application:**
   ```bash
   # Terminal 1: Backend
   cd server && source venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port 8787
   
   # Terminal 2: Frontend
   npm run dev
   ```

3. **Run tests:**
   ```bash
   # Run all tests
   python3 tests/utils/test_runner.py
   
   # Run specific test
   python3 tests/utils/test_runner.py --test-id TC_AUTH_001
   
   # Run by category
   python3 tests/utils/test_runner.py --category authentication
   ```

## Directory Structure

```
tests/
├── config/              # Configuration files
├── tests/              # Test files organized by category
│   ├── authentication/
│   ├── chat/
│   ├── isolation/
│   ├── crud/
│   └── integration/
├── fixtures/           # Base test classes and page objects
├── reports/             # Test execution reports
├── test-plans/          # Test plan JSON files
├── utils/               # Test runner and utilities
└── docs/                # Documentation
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Testing Guide](docs/TESTING_GUIDE.md) - How to write tests
- [Naming Conventions](docs/NAMING_CONVENTIONS.md) - Test naming standards
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Test Categories

- **Authentication** (`authentication/`): Login, logout, session management
- **Chat** (`chat/`): Chat functionality, messaging
- **Isolation** (`isolation/`): User data isolation, security
- **CRUD** (`crud/`): Create, read, update, delete operations
- **Integration** (`integration/`): End-to-end workflows

## Configuration

Edit configuration files in `tests/config/`:
- `config.json`: Test settings, timeouts, browser configuration
- `test-users.json`: Test user credentials
- `environments.json`: Environment-specific settings

## Test Reports

After running tests, reports are generated in `tests/reports/latest/`:
- `test_results.json`: Machine-readable JSON report
- `test_report.md`: Human-readable Markdown report
- `screenshots/`: Screenshots of failed tests

## Running Tests

### Command Line Options

```bash
python3 tests/utils/test_runner.py [OPTIONS]

Options:
  --category, -c      Test category to run
  --test-id, -t       Specific test ID (can be used multiple times)
  --pattern, -p       Regex pattern to match test IDs or names
  --environment, -e   Environment name (default: local)
  --parallel          Run tests in parallel
```

### Examples

```bash
# Run all authentication tests
python3 tests/utils/test_runner.py --category authentication

# Run specific test
python3 tests/utils/test_runner.py --test-id TC_AUTH_001

# Run tests matching pattern
python3 tests/utils/test_runner.py --pattern "AUTH"

# Run tests in parallel
python3 tests/utils/test_runner.py --parallel

# Run against staging environment
python3 tests/utils/test_runner.py --environment staging
```

## Writing Tests

See [TESTING_GUIDE.md](docs/TESTING_GUIDE.md) for detailed instructions.

### Basic Test Template

```python
"""
Test: TC_CATEGORY_ID - Test Name

Description: What the test verifies.

Category: category_name
Priority: High
Tags: [tag1, tag2]
"""

import asyncio
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from base_test import BaseTest
from page_objects import SignInPage, AppPage

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "utils"))
from config_loader import get_config_loader


async def run_test():
    """Execute test."""
    test = BaseTest(test_id="TC_CATEGORY_ID", test_name="Test Name")
    try:
        await test.setup()
        # Your test code here
        test.mark_passed()
    except Exception as e:
        test.mark_failed(str(e))
        raise
    finally:
        await test.teardown()


if __name__ == "__main__":
    asyncio.run(run_test())
```

## Contributing

When adding new tests:

1. Follow naming conventions (see [NAMING_CONVENTIONS.md](docs/NAMING_CONVENTIONS.md))
2. Place tests in appropriate category directory
3. Include complete documentation header
4. Use page objects for interactions
5. Record test steps
6. Update category README if needed

## Support

For issues or questions:
1. Check [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Review test reports for error details
3. Check application logs
4. Verify configuration is correct
