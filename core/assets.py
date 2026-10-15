"""Content-versioned asset URLs prevent stale JavaScript across releases."""

from functools import lru_cache
import hashlib
from pathlib import Path

STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"


@lru_cache(maxsize=256)
def fingerprint(path: Path, modified: int, size: int) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def static_asset(request, path: str):
    file = (STATIC_ROOT / path.lstrip("/")).resolve()
    if not file.is_relative_to(STATIC_ROOT):
        raise ValueError("Asset path must stay inside static directory")
    info = file.stat()
    version = fingerprint(file, info.st_mtime_ns, info.st_size)
    return request.url_for("static", path=path).include_query_params(v=version)
