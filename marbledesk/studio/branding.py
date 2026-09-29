"""User-facing application identity and bundled artwork."""
from pathlib import Path
import sys


APP_NAME = 'marbles by MJD'


def icon_path():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    return root / 'assets' / 'marbles-icon.png'
