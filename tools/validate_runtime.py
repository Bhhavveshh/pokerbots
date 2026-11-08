"""Run full duplicate matches through a persistent, guarded JSONL subprocess."""

import argparse
import json
import queue
import random
import subprocess
import sys
import threading
import time
from dataclasses import asdict
from pathlib import Path

from pokerbot.bots import BOT_TYPES, BaseBot, register_strategies
from pokerbot.game import Action, Engine
from tools.runtime_support import one_cpu, peak_memory_bytes

ROOT = Path(__file__).resolve().parents[1]
register_strategies()


def validate(opponent, pairs, seed):
    affinity = one_cpu()
    start = time.perf_counter()
    child = subprocess.Popen([sys.executable, "-B", str(ROOT / "tools/guarded_bot.py")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, bufsize=1, cwd=ROOT)
    replies = queue.Queue()
    errors = []

    def read_stdout():
        for line in child.stdout:
            replies.put(line)
        replies.put(None)

    def read_stderr():
        for line in child.stderr:
            if len(errors) < 20:
                errors.append(line.strip())

    threading.Thread(target=read_stdout, daemon=True).start()
    stderr_thread = threading.Thread(target=read_stderr, daemon=True)
    stderr_thread.start()
    transport_seconds = 0.0
    max_response = 0.0

    def send(message):
        nonlocal transport_seconds, max_response
        tick = time.perf_counter()
        child.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        child.stdin.flush()
        try:
            line = replies.get(timeout=3)
        except queue.Empty:
            raise TimeoutError("bot did not respond within 3 seconds") from None
        if line is None:
            raise RuntimeError("bot process ended unexpectedly")
        response = json.loads(line)
        if "error" in response:
            raise ValueError(response)
        duration = time.perf_counter() - tick
        transport_seconds += duration
        max_response = max(max_response, duration)
        if transport_seconds >= 60:
            raise TimeoutError("60-second transport-inclusive time bank exhausted")
        return response

    class Adapter(BaseBot):
        def act(self, obs):
            response = send({"type": "act", "observation": asdict(obs),
                             "remaining_seconds": max(0, 60 - transport_seconds)})
            return Action(response["action"], response.get("amount", 0))

        def finish(self, result, hand_id, seat):
            send({"type": "hand_end", "hand_id": hand_id, "player": seat,
                  "board": result.board, "history": [asdict(e) for e in result.history]})

    try:
        send({"type": "reset", "seed": seed + 101, "time_bank": 60,
              "expected_hands": pairs * 2})
        startup_seconds = time.perf_counter() - start
        bot, villain = Adapter(), BOT_TYPES[opponent](seed + 307)
        rng = random.Random(seed)
        engine = Engine()
        total = 0
        for pair in range(pairs):
            deck = list(range(52))
            rng.shuffle(deck)
            first = engine.play((bot, villain), deck, button=pair % 2, hand_id=pair * 2)
            bot.finish(first, pair * 2, 0)
            second = engine.play((villain, bot), deck, button=pair % 2, hand_id=pair * 2 + 1)
            bot.finish(second, pair * 2 + 1, 1)
            total += first.profits[0] + second.profits[1]
        peak = peak_memory_bytes(child)
        if peak >= 1024 ** 3:
            raise MemoryError("observed peak working set exceeded 1 GiB")
        child.stdin.close()
        return_code = child.wait(timeout=3)
        stderr_thread.join(timeout=1)
        if return_code != 0 or errors:
            raise AssertionError({"exit": return_code, "stderr": errors})
        return {"opponent": opponent, "hands": pairs * 2, "seed": seed,
                "profit_chips": total, "bb_per_hand": total / (pairs * 4),
                "transport_inclusive_bank_seconds": transport_seconds,
                "startup_seconds": startup_seconds, "max_response_seconds": max_response,
                "process_peak_working_set_bytes": peak, "affinity": affinity,
                "wall_seconds_including_engine_and_opponent": time.perf_counter() - start,
                "errors": errors, "passed": True,
                "limitations": "Windows audit guards and affinity; not the organizer's Linux sandbox. "
                               "Transport time includes reset, startup wait, hand-end messages and parent JSON work; "
                               "it excludes time spent simulating the engine and opponent."}
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=3)
        for stream in (child.stdin, child.stdout, child.stderr):
            if stream and not stream.closed:
                stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opponent", choices=BOT_TYPES, default="calling")
    parser.add_argument("--pairs", type=int, default=500)
    parser.add_argument("--seed", type=int, default=990100)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.pairs < 1:
        parser.error("pairs must be positive")
    report = validate(args.opponent, args.pairs, args.seed)
    Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
