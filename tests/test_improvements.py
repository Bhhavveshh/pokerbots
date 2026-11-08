import time
import unittest
import json
import random
import subprocess
import sys
from pathlib import Path

from pokerbot.experimental_agent import Config, DiscardBot, select_pair
from tests.test_official import cards
from tools.experiments import paired
from tools.experiments import entry, ROOT
from tests.test_official import init, new_hand, request
from pokerbot.responses import raise_value
from pokerbot.preflop import canonical


class ImprovementTests(unittest.TestCase):
    def test_discard_selection_keeps_highest_supported_mean_not_last_candidate(self):
        pairs = ((1, 2), (1, 3), (2, 3))
        best, means = select_pair(pairs, pairs[0], [[0.2] * 32, [0.9] * 32, [0.6] * 32])
        self.assertEqual(best, 1)
        self.assertGreater(means[1], means[2])

    def test_independent_opponents_do_not_reuse_our_policy_and_emit_legal_actions(self):
        from pokerbot.benchmarks import EquityPolicy
        from pokerbot.protocol import legal_reply
        for mode in ("equity", "polar"):
            policy = EquityPolicy(mode, samples=16)
            policy.handle(init())
            policy.handle(new_hand())
            req = request()
            self.assertTrue(legal_reply(policy.handle(req), req))
            discard = {"type":"discard_request", "hole_cards":["As","Kd","7c"],
                       "board":["Ah","Qd","2s"]}
            self.assertIn(policy.handle(discard)["card"],discard["hole_cards"])
        with self.assertRaises(ValueError):
            EquityPolicy("unknown")

    def test_exact_river_has_all_903_legal_pairs_and_board_tie(self):
        bot = DiscardBot(seed=72, config=Config(exact_river=True))
        bot.new_hand(1, cards("2c 3d 4h"), True)
        bot.reveal_discard(cards("2c 3d"), cards("5h")[0])
        rows = bot.sample_equity(cards("As Ks Qs Js Ts"), (), time.perf_counter() + 1)
        self.assertEqual(len(rows), 903)
        self.assertEqual(len(set(bot.belief.hands)), 903)
        self.assertAlmostEqual(sum(row[2] for row in rows), 1)
        self.assertAlmostEqual(bot.last_equity, 0.5)

    def test_exact_weighted_river_matches_organizer_oracle_and_is_repeatable(self):
        from tools.official_match import load_engine
        from pokerbot.cards import card_name
        bot = DiscardBot(seed=51, config=Config(exact_river=True, discard_signal=False))
        bot.new_hand(1, cards("As Ad 7c"), True)
        bot.reveal_discard(cards("As Ad"), cards("Qs")[0])
        board = cards("2h 3c 9d Th Kc")
        bot.sample_equity(board, (), time.perf_counter() + 1)
        engine = load_engine()
        public = [card_name(c) for c in board]
        ours = engine.best_hand([card_name(c) for c in bot.hole], public)
        total = expected = 0
        for hand, weight in zip(bot.belief.hands, bot.belief.weights):
            theirs = engine.best_hand([card_name(c) for c in hand], public)
            expected += weight * (1 if ours > theirs else 0.5 if ours == theirs else 0)
            total += weight
        first = bot.last_equity
        self.assertAlmostEqual(first, expected / total)
        bot.rng.seed(99999)
        bot.sample_equity(board, (), time.perf_counter() + 1)
        self.assertEqual(bot.last_equity, first)

    def test_response_tree_averages_hidden_worlds_before_hero_choice(self):
        req = {"pot":10,"my_bet":0,"opp_bet":0,"raises_left":4,"max_raise":100}
        rows = [(0, 0.99, 0.5), (1, 0.99, 0.5)]
        # With 50% equity and symmetric payments, every called size yields +P/2.
        # Choosing call/fold separately after seeing each hidden hand would falsely
        # report a higher value, a common perfect-information search bug.
        self.assertAlmostEqual(raise_value(req, 10, rows, lambda f,p:1, tree=True), 5)
        self.assertAlmostEqual(raise_value(req, 10, rows, lambda f,p:1, tree=False), 5)

    def test_suit_isomorphic_preflop_keys(self):
        from itertools import permutations
        original = cards("As Ah Kd")
        expected = canonical(original)
        for mapping in permutations(range(4)):
            transformed = tuple((c // 4) * 4 + mapping[c % 4] for c in original)
            self.assertEqual(canonical(transformed), expected)

    def test_preflop_data_covers_all_raw_hands_and_orders_extremes(self):
        from pokerbot.preflop import table, strength
        values = table()
        self.assertEqual(len(values), 1755)
        self.assertEqual(sum(row["multiplicity"] for row in values.values()), 22100)
        self.assertGreater(strength(cards("As Ah Kd")), strength(cards("2c 3d 7h")))
        self.assertTrue(all(0 <= row["equity"] <= 1 for row in values.values()))

    def test_fixed_work_replay_fixture_matches_frozen_v1_replies(self):
        rng = random.Random(5097)
        messages = [init()]
        for hand in range(1, 13):
            deck = rng.sample(range(52), 6)
            from pokerbot.cards import card_name
            hole = [card_name(c) for c in deck[:3]]
            board = [card_name(c) for c in deck[3:]]
            messages += [new_hand(hole, hand), request(hand_id=hand),
                         request(hand_id=hand, street="flop", board=board, pot=12,
                                 my_bet=0, opp_bet=0, to_call=0, my_stack=194, opp_stack=194,
                                 legal_actions=["check", "raise"], min_raise=2, max_raise=194,
                                 raises_left=4, history=[
                                     {"street":"preflop","actor":"me","action":"raise","amount":6},
                                     {"street":"preflop","actor":"opp","action":"call","amount":6},
                                     {"street":"flop","actor":"opp","action":"check"}]),
                         {"type":"discard_request","hand_id":hand,"hole_cards":hole,"board":board,
                          "pot":12,"my_stack":194,"opp_stack":194,"time_left_ms":30000}]
        messages.append({"type":"match_end","reason":"complete"})
        data = "".join(json.dumps(m) + "\n" for m in messages)
        results = []
        for script in (entry("v1", timeless=True), entry("v1a", {"consistent_flop": False}, timeless=True)):
            result = subprocess.run([sys.executable, "-B", str(script)], input=data,
                                    text=True, capture_output=True, cwd=ROOT, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            results.append(result.stdout)
        self.assertEqual(results[0], results[1])

    def test_planned_discard_matches_flop_equity_policy(self):
        bot = DiscardBot(seed=73, config=Config(consistent_flop=True, samples=32, particles=32))
        original = cards("Qh Jh 4c")
        flop = cards("Th 9h 2c")
        bot.new_hand(1, original, True)
        bot.sample_equity(flop, (), time.perf_counter() + 10)
        self.assertEqual(len(bot.planned_keep), 2)
        retained = set(original) - {bot.choose_discard(flop, 30000)}
        self.assertEqual(retained, set(bot.planned_keep))
        before = bot.planned_keep
        bot.sample_equity(flop, (), time.perf_counter() + 10)
        self.assertEqual(bot.planned_keep, before)
        bot.new_hand(2, cards("As Kd 7c"), False)
        self.assertIsNone(bot.planned_keep)

    def test_paired_comparison_requires_same_panel_and_keeps_seed_blocks(self):
        def report(points):
            return {"runs": [{"opponent": opp, "seed": seed, "hands_scheduled": 400,
                              "match_points": points, "bb_per_hand": points}
                             for opp in ("a", "b") for seed in ("x", "y")]}
        result = paired(report(0), report(1))
        self.assertEqual(result["matched_matches"], 4)
        self.assertEqual(result["seed_blocks"], 2)
        self.assertEqual(result["point_delta_95pct_bootstrap"], [1, 1])
        wrong = report(1)
        wrong["runs"].pop()
        with self.assertRaises(ValueError):
            paired(report(0), wrong)


if __name__ == "__main__":
    unittest.main()
