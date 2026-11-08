"""Build deterministic runtime and reproducibility archives; exclude local tools/downloads."""

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_zip(destination, paths):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(2026, 11, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise AssertionError("corrupt archive")
    return {"path": destination.name, "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


def main():
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    production = [ROOT / "bot.py", ROOT / "PROTOCOL.md"] + [
        p for p in (ROOT / "pokerbot").glob("*.py") if p.name != "benchmark.py"]
    source = [ROOT / name for name in ("bot.py", "README.md", "PLAN.md", "PROTOCOL.md", "RESULTS.md")]
    for directory in ("pokerbot", "tests", "tools"):
        source.extend((ROOT / directory).glob("*.py"))
    source.extend((ROOT / "reports").glob("*.json"))
    runtime = destination / "pokerbot-runtime.zip"
    archives = [write_zip(runtime, production), write_zip(destination / "pokerbot-source.zip", source)]
    # Import from the runtime ZIP before any workspace path. Check the package's
    # actual origin so the private interpreter's search paths cannot mask omissions.
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, sys.argv[1]); "
            "import pokerbot; assert pokerbot.__file__.startswith(sys.argv[1]); "
            "from pokerbot.protocol import main; main()")
    request = {"type": "act", "observation": {
        "hand_id": 0, "player": 0, "button": 0, "hole": ["As", "Kd"], "board": [],
        "stacks": [199, 198], "pot": 3, "street": 0, "contributions": [1, 2],
        "call_cost": 1, "min_raise_to": 4, "max_raise_to": 200, "big_blind": 2, "history": []}}
    result = subprocess.run([sys.executable, "-B", "-c", code, str(runtime)],
                            input=json.dumps(request) + "\n", text=True,
                            capture_output=True, cwd=destination, timeout=10)
    if result.returncode or result.stderr:
        raise AssertionError({"exit": result.returncode, "stderr": result.stderr})
    response = json.loads(result.stdout)
    if response != {"action": "raise", "amount": 5}:
        raise AssertionError(response)
    with zipfile.ZipFile(runtime) as archive:
        if archive.testzip() is not None:
            raise AssertionError("corrupt runtime archive")
        for path in production:
            if archive.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise AssertionError("archive differs from workspace source")
    manifest = {"archives": archives, "python": sys.version,
                "runtime_archive_import_and_decision_test_passed": True,
                "status": "Development bundle. Official protocol and rule verification still required."}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
