import sys
from pathlib import Path

# Compute project root (one level up from tests/)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# Prepend to sys.path so pytest can import app.*
sys.path.insert(0, str(PROJECT_ROOT))