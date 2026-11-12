"""Download the official data set of the challenge into data/ and check its integrity.

The CSV files are not committed to this repository (see "Data" in the README). This script
takes the archive from the official fulll repository, at a pinned commit, checks its SHA-256
and extracts the three expected files only.

Usage: python scripts/fetch_data.py
"""

import hashlib
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

COMMIT = "68d9abfd8bfc47f8c240bcd9b0bf305886121004"
URL = (
    f"https://raw.githubusercontent.com/fulll/hiring/{COMMIT}/DataEngineer/Junior/Bike_raw_data.zip"
)
ARCHIVE_SHA256 = "add3f3f54b369a3b3a142f3fcbc874cbea1a826c34df808ecd731b7c04270c31"
FILES_SHA256 = {
    "chicago.csv": "cb049fb75cf0962ac1104879cdf6ad1f1bfb1e02d2c63bbca8cc06d99c8a61a0",
    "new_york_city.csv": "99bb98198480809f1da599d3a0ceb0b9c952e9e199435487799073ccfece29ff",
    "washington.csv": "69d1fc252dc202efc0879484a514a488425c9b10efcc33b1f4a45264fa5dbb80",
}
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def in_place():
    """True when the three files are already there with the expected content."""
    return all(
        (DATA_DIR / name).is_file() and sha256((DATA_DIR / name).read_bytes()) == digest
        for name, digest in FILES_SHA256.items()
    )


def main():
    if in_place():
        print(f"Data already in place in {DATA_DIR}")
        return 0

    print(f"Downloading {URL}")
    with urllib.request.urlopen(URL, timeout=120) as response:
        archive = response.read()
    if sha256(archive) != ARCHIVE_SHA256:
        print("The archive does not have the expected SHA-256, nothing written.", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        # Members are read by name: the __MACOSX entries of the archive are ignored and no
        # path stored in the archive is ever used to write a file.
        for name, digest in FILES_SHA256.items():
            content = bundle.read(name)
            if sha256(content) != digest:
                print(f"{name} does not have the expected SHA-256.", file=sys.stderr)
                return 1
            (DATA_DIR / name).write_bytes(content)
            print(f"  {name}: {len(content):,} bytes")
    print(f"Data ready in {DATA_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
