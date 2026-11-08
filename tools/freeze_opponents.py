"""Freeze independent benchmark policies before opening final evaluation seeds."""

import hashlib
import json
import zipfile

from tools.experiments import ROOT


def main():
    path = ROOT / "experiments/opponents/independent_v1.zip"
    if path.exists():
        raise ValueError("Opponent archives are immutable")
    path.parent.mkdir(parents=True, exist_ok=True)
    files = ("pokerbot/__init__.py", "pokerbot/cards.py", "pokerbot/benchmarks.py")
    hashes = {f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in files:
            archive.writestr(filename, (ROOT / filename).read_bytes())
        archive.writestr("snapshot.json", json.dumps({"files": hashes}, indent=2))
    print(path)


if __name__ == "__main__":
    main()
