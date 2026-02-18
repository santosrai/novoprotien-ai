"""Root conftest for server tests."""
import sys
from pathlib import Path

# Ensure the project root is on sys.path so that `server.*` imports work
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
