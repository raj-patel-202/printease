"""Vendor a pinned Mozilla PDF.js npm release, verifying registry SHA-512 integrity.

Downloads data only; never runs npm lifecycle scripts or downloaded code.
"""

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

VERSION = "6.4.299"


def main():
    root = Path(__file__).resolve().parent.parent / "static/js/vendor/pdfjs"
    with urlopen(f"https://registry.npmjs.org/pdfjs-dist/{VERSION}", timeout=30) as response:
        metadata = json.load(response)
    with urlopen(metadata["dist"]["tarball"], timeout=60) as response:
        payload = response.read()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
    if integrity != metadata["dist"]["integrity"]:
        raise ValueError("PDF.js package integrity mismatch")
    checksums = {}
    with tarfile.open(fileobj=BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            relative = member.name.removeprefix("package/")
            if relative not in {"build/pdf.min.mjs", "build/pdf.worker.min.mjs", "LICENSE"} and not relative.startswith(
                ("wasm/", "cmaps/", "standard_fonts/")
            ):
                continue
            target = (root / relative).resolve()
            if not target.is_relative_to(root.resolve()) or not member.isfile():
                continue
            content = archive.extractfile(member).read()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            checksums[relative] = hashlib.sha256(content).hexdigest()
    (root / "manifest.json").write_text(
        json.dumps(
            dict(version=VERSION, source=metadata["dist"]["tarball"], integrity=integrity, sha256=checksums), indent=2
        ),
        encoding="utf-8",
    )
    print(f"Vendored PDF.js {VERSION}: {len(checksums)} files; SHA-512 verified")


if __name__ == "__main__":
    main()
