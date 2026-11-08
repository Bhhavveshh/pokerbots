"""Offline solver validation, separate from actual full-match win-rate tests."""

import hashlib
import json
import time

from pokerbot.cfr import CFR, OneBetGame, kuhn_game
from tools.experiments import ROOT


def measure(name, game, iterations):
    solver = CFR(game)
    before = game.exploitability(solver.current())
    start = time.perf_counter()
    policy = solver.train(iterations)
    return {"game": name, "iterations": iterations, "seconds": time.perf_counter() - start,
            "value_player0": game.value(policy), "initial_exploitability": before,
            "final_exploitability": game.exploitability(policy), "policy": policy}


def main():
    rows = [measure("Kuhn poker", kuhn_game(), 10000)]
    if abs(rows[0]["value_player0"] + 1 / 18) > 0.002 or rows[0]["final_exploitability"] > 0.01:
        raise AssertionError("CFR failed the known Kuhn equilibrium")
    # Restricted river abstractions with several stack-to-pot ratios. These are
    # solver calibration games, not independent opponents or full Hold'em Nash tests.
    joint = [[1 / 16] * 4 for _ in range(4)]
    equity = [[1 if i > j else 0.5 if i == j else 0 for j in range(4)] for i in range(4)]
    for bet in (0.25, 0.75, 2):
        for reply in (True, False):
            rows.append(measure(f"four buckets: bet/pot={bet}, OOP={reply}",
                                OneBetGame(joint, equity, 1, bet, reply), 5000))
    report = {"method": "Vanilla CFR with counterfactual reach-weighted regrets and average strategies",
              "known_kuhn_value": -1 / 18, "exploitability_definition": "half of the sum of both best-response values",
              "source_sha256": hashlib.sha256((ROOT / "pokerbot/cfr.py").read_bytes()).hexdigest(),
              "games": rows, "full_game_equilibrium_claim": False,
              "limitations": "Public-range samples, four strength buckets, one bet size, no raises. Online solve is time-bounded and is not a safe subgame replacement theorem."}
    path = ROOT / "reports/improvements/cfr_validation.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{k:v for k,v in row.items() if k != "policy"} for row in rows], indent=2))


if __name__ == "__main__":
    main()
