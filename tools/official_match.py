"""Metrics wrapper around the UNMODIFIED organizer match runner, clocks enabled."""

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import platform
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.runtime_support import one_cpu, peak_memory_bytes

ENGINE_PATH = ROOT / "official/Starter_Kit/engine.py"
RUNTIME_FILES = ("bot.py", "pokerbot/__init__.py", "pokerbot/__main__.py",
                 "pokerbot/cards.py", "pokerbot/discard.py", "pokerbot/agent.py", "pokerbot/protocol.py")


def load_engine():
    spec = importlib.util.spec_from_file_location("organizer_engine", ENGINE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def snapshot():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in RUNTIME_FILES + ("official/Starter_Kit/engine.py",)}


def run_match(bot_a, bot_b, stage, seed, hands=None, log_dir=None):
    engine = load_engine()
    log_dir = Path(log_dir) if log_dir else ROOT / "tmp/official_runs" / str(seed)
    args = SimpleNamespace(stage=stage, hands=hands, seed=str(seed), verbose=False,
                           log_dir=str(log_dir), bot_a=str(Path(bot_a).resolve()),
                           bot_b=str(Path(bot_b).resolve()), python=sys.executable,
                           no_time_limits=False)

    class RecordingMatch(engine.Match):
        def __init__(self, args):
            super().__init__(args)
            self.metrics = []
            self.report = None

        def launch(self, leg):
            bots = super().launch(leg)
            for bot in bots:
                metric = {"bot": bot.name, "leg": leg + 1, "peak_working_set_bytes": 0,
                          "requests": 0, "max_charged_reply_seconds": 0}
                self.metrics.append(metric)
                original_wait, original_close = bot.wait_reply, bot.close

                def wait(deadline, bot=bot, metric=metric, original=original_wait):
                    before = bot.time_used_s
                    result = original(deadline)
                    metric["requests"] += 1
                    metric["max_charged_reply_seconds"] = max(
                        metric["max_charged_reply_seconds"], bot.time_used_s - before)
                    if metric["requests"] % 32 == 1:
                        try:
                            metric["peak_working_set_bytes"] = max(
                                metric["peak_working_set_bytes"], peak_memory_bytes(bot.proc))
                        except OSError:
                            # The child may have exited on a forfeit; that failure
                            # is reported by the authoritative runner, not hidden.
                            metric["memory_measurement_unavailable"] = True
                    return result

                def close(bot=bot, metric=metric, original=original_close):
                    original()
                    metric.update(charged_seconds=bot.time_used_s,
                                  notices=bot.notices, stderr_bytes=bot.stderr_bytes,
                                  exit_code=bot.proc.returncode)

                bot.wait_reply, bot.close = wait, close
            return bots

        def summary(self, totals, played, forfeits, forfeit_at):
            super().summary(totals, played, forfeits, forfeit_at)
            delta = totals[0]
            if len(forfeits) == 2:
                delta = 0
            elif forfeits:
                delta = -self.cap if forfeits[0][0].name == "A" else self.cap
            self.report = {
                "seed": str(seed), "stage": stage, "hands_scheduled": self.hands,
                "hands_played": played, "profit_chips": delta,
                "raw_chips": totals[0], "bb_per_hand": delta / (2 * self.hands),
                "capped_delta": max(-self.cap, min(self.cap, delta)),
                "capped_chips_per_hand": max(-self.cap, min(self.cap, delta)) / self.hands,
                "match_points": 1 if delta > 0 else 0.5 if delta == 0 else 0,
                "candidate_notices": self.notice_count[0],
                "opponent_notices": self.notice_count[1],
                "forfeits": [{"bot": bot.name, "reason": reason} for bot, reason in forfeits],
                "forfeit_at": forfeit_at, "legs": self.metrics,
                "candidate_stderr_bytes": sum(m["stderr_bytes"] for m in self.metrics if m["bot"] == "A"),
                "log_dir": str(log_dir.relative_to(ROOT)) if log_dir.is_relative_to(ROOT) else str(log_dir),
            }

    match = RecordingMatch(args)
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        match.run()
    report = match.report
    report["runner_summary"] = captured.getvalue().strip()
    return report


def opponent_path(name):
    if name == "starter":
        return ROOT / "official/Starter_Kit/bot.py"
    if name == "organizer_random":
        return ROOT / "official/Starter_Kit/example_bots/random_bot.py"
    return ROOT / "tests/opponents" / (name + ".py")


def league(opponents, matches, stage, seed_prefix, label, candidate=None, hands=None):
    source = snapshot()
    rows = []
    for opponent in opponents:
        runs = []
        for i in range(matches):
            seed = f"{seed_prefix}-{i}"
            log = ROOT / "tmp/official_runs" / label / opponent / str(i)
            run = run_match(candidate or ROOT / "bot.py", opponent_path(opponent), stage,
                            seed, hands, log)
            runs.append(run)
            if run["forfeits"] or run["candidate_notices"] or run["candidate_stderr_bytes"]:
                raise RuntimeError(f"Official integration failure; inspect {log}")
        scores = [r["bb_per_hand"] for r in runs]
        row = {"opponent": opponent, "runs": runs,
               "wins": sum(r["match_points"] == 1 for r in runs),
               "draws": sum(r["match_points"] == 0.5 for r in runs),
               "losses": sum(r["match_points"] == 0 for r in runs),
               "mean_bb_per_hand": statistics.mean(scores),
               "match_point_rate": statistics.mean(r["match_points"] for r in runs),
               "approx_95pct_half_width": (1.96 * statistics.stdev(scores) / math.sqrt(matches)
                                          if matches > 1 else None)}
        rows.append(row)
        print(f"{label} vs {opponent}: {row['wins']}/{matches} wins, "
              f"{row['mean_bb_per_hand']:+.4f} BB/hand", flush=True)
    if snapshot() != source:
        raise RuntimeError("core source changed during evaluation")
    return {"label": label, "variant": "Discard Hold'em", "protocol": "1.0",
            "stage": stage, "seed_prefix": seed_prefix, "matches_per_opponent": matches,
            "python": sys.version, "platform": platform.platform(), "source_sha256": source,
            "clocks_enabled": True, "results": rows,
            "limitations": ["Local organizer runner on Windows, not the server sandbox.",
                            "Locally authored synthetic opponents, some share policy code.",
                            "Normal-approximation intervals over whole matches; small samples.",
                            "The organizer random bot is unseeded; our other opponents are seeded.",
                            "Legacy two-card Hold'em reports are not evidence for this variant."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opponents", nargs="+", default=["starter", "tight", "aggressive", "reference"])
    parser.add_argument("--matches", type=int, default=4)
    parser.add_argument("--stage", type=int, choices=(1, 2), default=1)
    parser.add_argument("--seed-prefix", default="discard-dev")
    parser.add_argument("--label", default="development")
    parser.add_argument("--candidate")
    parser.add_argument("--hands", type=int)
    parser.add_argument("--one-cpu", action="store_true")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.matches < 1:
        parser.error("matches must be positive")
    affinity = one_cpu() if args.one_cpu else None
    report = league(args.opponents, args.matches, args.stage, args.seed_prefix,
                    args.label, args.candidate, args.hands)
    report["affinity"] = affinity
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
