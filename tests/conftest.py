import sys
from pathlib import Path


# Ensure the 'vibe' directory (parent of this file) is importable when running pytest from repo root
THIS_DIR = Path(__file__).resolve().parent
VIBE_DIR = THIS_DIR.parent
if str(VIBE_DIR) not in sys.path:
    sys.path.insert(0, str(VIBE_DIR))

