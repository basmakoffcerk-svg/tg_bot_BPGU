import os
import sys
from pathlib import Path

# Ensure app and root modules can be imported
_current_dir = Path(__file__).resolve().parent
_root_dir = _current_dir.parent
for p in [_root_dir, _current_dir]:
    str_p = str(p)
    if str_p not in sys.path:
        sys.path.insert(0, str_p)

from app.api.app import app



