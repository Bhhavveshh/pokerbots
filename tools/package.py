"""Create a <=5 MB official submission ZIP and verify it with the supplied runner."""

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.official_match import RUNTIME_FILES, run_match


def write_zip(destination, paths):
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), date_time=(2026, 11, 8, 0, 0, 0))
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
    production = [ROOT / name for name in RUNTIME_FILES]
    runtime = destination / "discard-holdem-submission.zip"
    runtime_info = write_zip(runtime, production)
    if runtime_info["bytes"] > 5_000_000:
        raise AssertionError("submission exceeds 5 MB")
    (destination / "pokerbot-runtime.zip").write_bytes(runtime.read_bytes())
    with zipfile.ZipFile(runtime) as archive:
        if "bot.py" not in archive.namelist():
            raise AssertionError("bot.py must be at ZIP root")
        for path in production:
            if archive.read(path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise AssertionError("archive differs from runtime source")
    # Force imports from the ZIP, then assert their actual source. This prevents
    # the private interpreter's workspace search path from masking missing files.
    code = ("import sys; sys.dont_write_bytecode=True; sys.path.insert(0, sys.argv[1]); "
            "import pokerbot; assert pokerbot.__file__.startswith(sys.argv[1]); "
            "from pokerbot.protocol import main; main()")
    messages = [
        {"type": "init", "protocol_version": "1.0", "total_hands": 200,
         "starting_stack": 200, "small_blind": 1, "big_blind": 2,
         "time_bank_ms": 30000, "per_response_ms": 5000},
        {"type": "new_hand", "hand_id": 1, "seat": "button", "hole_cards": ["As", "Kd", "7c"],
         "stack": 200, "opp_stack": 200},
        {"type": "action_request", "hand_id": 1, "street": "preflop", "board": [],
         "pot": 3, "my_bet": 1, "opp_bet": 2, "to_call": 1, "my_stack": 199, "opp_stack": 198,
         "legal_actions": ["fold", "call", "raise"], "min_raise": 4, "max_raise": 200,
         "raises_left": 3, "history": [], "time_left_ms": 30000},
        {"type": "match_end", "reason": "complete"}]
    process = subprocess.run([sys.executable, "-B", "-c", code, str(runtime)],
                             input="".join(json.dumps(m) + "\n" for m in messages),
                             text=True, capture_output=True, cwd=destination, timeout=10)
    if process.returncode or process.stderr:
        raise AssertionError({"exit": process.returncode, "stderr": process.stderr})
    if json.loads(process.stdout) != {"type": "action", "action": "raise", "amount": 6}:
        raise AssertionError(process.stdout)
    wrapper = ROOT / "tmp/package_verification/bot.py"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text("import sys\nsys.dont_write_bytecode = True\n"
                       f"sys.path.insert(0, {str(runtime)!r})\n"
                       "import pokerbot\n"
                       f"assert pokerbot.__file__.startswith({str(runtime)!r})\n"
                       "from pokerbot.protocol import main\nmain()\n", encoding="utf-8")
    check = run_match(wrapper, ROOT / "official/Starter_Kit/bot.py", 1, "discard-package-check",
                      hands=40, log_dir=ROOT / "tmp/package_verification/logs")
    if check["forfeits"] or check["candidate_notices"] or check["candidate_stderr_bytes"]:
        raise AssertionError("packaged bot failed the organizer runner")
    report_path = ROOT / "reports/discard_holdem/package.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(check, indent=2) + "\n", encoding="utf-8")
    source = [ROOT / name for name in (".gitignore", ".gitattributes", "bot.py", "README.md",
                                       "PLAN.md", "PROTOCOL.md", "RESULTS.md")]
    for directory in ("pokerbot", "tests", "tools"):
        source.extend(p for p in (ROOT / directory).rglob("*.py") if "__pycache__" not in p.parts)
    source.extend(p for p in (ROOT / "official").rglob("*")
                  if p.is_file() and "__pycache__" not in p.parts)
    source.extend((ROOT / "reports").rglob("*.json"))
    source.extend((ROOT / "reports").rglob("*.md"))
    archives = [runtime_info, write_zip(destination / "pokerbot-source.zip", source)]
    manifest = {"archives": archives, "python": sys.version, "variant": "Discard Hold'em",
                "runtime_zip_import_and_protocol_test_passed": True,
                "official_runner_package_test_hands": check["hands_played"],
                "status": "Official local-runner checks passed. Organizer server sandbox remains unverified."}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
