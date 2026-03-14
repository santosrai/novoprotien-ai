"""Auto-mark all tests in this directory as integration tests."""
import pytest

# Apply 'integration' marker to every test in this directory
pytestmark = pytest.mark.integration
