"""Compatibility entry point; use python create_admin.py for new installations."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from create_admin import create_admin  # noqa: E402

if __name__ == "__main__":
    asyncio.run(create_admin())
