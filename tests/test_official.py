import contextlib
import io
import json
import random
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pokerbot.agent import Belief, Config, DiscardBot, decode_history
from pokerbot.cards import card_name, evaluate, parse_card
from pokerbot.discard import keep_fast, lowest_discard
from pokerbot.protocol import ProtocolSession, legal_reply
from tools.official_match import load_engine

ROOT = Path(__file__).resolve().parents[1]


def cards(text):
    return tuple(parse_card(c) for c in text.split())


def init(total=200, bank=30000):
    return {"type": "init", "protocol_version": "1.0", "total_hands": total,
            "starting_stack": 200, "small_blind": 1, "big_blind": 2,
            "time_bank_ms": bank, "per_response_ms": 5000}


def new_hand(hole=("As", "Kd", "7c"), hand_id=1):
    return {"type": "new_hand", "hand_id": hand_id, "seat": "button",
            "hole_cards": list(hole), "stack": 200, "opp_stack": 200}


def request(**changes):
    msg = {"type": "action_request", "hand_id": 1, "street": "preflop", "board": [],
           "pot": 3, "my_bet": 1, "opp_bet": 2, "to_call": 1,
           "my_stack": 199, "opp_stack": 198, "legal_actions": ["fold", "call", "raise"],
           "min_raise": 4, "max_raise": 200, "raises_left": 3, "history": [], "time_left_ms": 30000}
    msg.update(changes)
    return msg


class OfficialProtocolTests(unittest.TestCase):
    def setUp(self):
        self.session = ProtocolSession(seed=731)
        self.session.handle(init())
        self.session.handle(new_hand())

    def test_silence_on_notifications_and_unknown_fields(self):
        self.assertIsNone(self.session.handle({"type": "future_notification", "data": 7}))
        self.assertIsNone(self.session.handle({"type": "notice", "code": "test"}))
        req = request(future_field={"new": True})
        self.assertTrue(legal_reply(self.session.handle(req), req))

    def test_raise_cap_and_short_allin_bounds(self):
        for low, high, left, legal in ((None, None, 0, ["fold", "call"]),
                                      (200, 200, 1, ["fold", "call", "raise"])):
            req = request(my_bet=140, opp_bet=180, to_call=40,
                          my_stack=60, opp_stack=20, pot=320,
                          min_raise=low, max_raise=high, raises_left=left, legal_actions=legal)
            reply = self.session.handle(req)
            self.assertTrue(legal_reply(reply, req))
        self.assertEqual(self.session.error_count, 0)

    def test_discard_is_answered_when_allin(self):
        self.session.handle(new_hand(("As", "Ad", "5c")))
        req = {"type": "discard_request", "hand_id": 1, "hole_cards": ["As", "Ad", "5c"],
               "board": ["7c", "Kd", "2h"], "pot": 400, "my_stack": 0, "opp_stack": 0,
               "time_left_ms": 30000}
        reply = self.session.handle(req)
        self.assertEqual(reply["type"], "discard")
        self.assertIn(reply["card"], req["hole_cards"])
        self.assertEqual(self.session.error_count, 0)

    def test_public_discard_changes_state_and_blocks_cards(self):
        self.session.bot.board = cards("Ah 7d 2s")
        self.session.handle({"type": "discard_result", "hand_id": 1,
                             "my_discard": "Kd", "opp_discard": "Qs", "hole_cards": ["As", "7c"]})
        self.assertEqual(self.session.bot.hole, cards("As 7c"))
        self.assertEqual(self.session.bot.opponent_discard, parse_card("Qs"))
        self.assertIsNone(self.session.bot.belief)

    def test_terminal_folds_count_once_and_init_resets_learning(self):
        history = [{"street": "preflop", "actor": "me", "action": "raise", "amount": 6},
                   {"street": "preflop", "actor": "opp", "action": "fold"}]
        result = {"type": "hand_result", "hand_id": 1, "result": "fold", "net": 2,
                  "board": [], "history": history}
        self.session.handle(result)
        self.session.handle(result)
        self.assertEqual(self.session.bot.model.folds[0], 1)
        self.session.handle(new_hand(hand_id=2))
        self.assertEqual(self.session.bot.model.folds[0], 1)
        self.session.handle(init(500, 75000))
        self.assertEqual(self.session.bot.model.folds[0], 0)
        self.assertEqual(self.session.bot.total_hands, 500)

    def test_exhausted_time_uses_legal_action_and_discard(self):
        req = request(time_left_ms=0)
        self.assertEqual(self.session.handle(req), {"type": "action", "action": "fold"})
        req = {"type": "discard_request", "hand_id": 1, "hole_cards": ["As", "Kd", "7c"],
               "board": ["Ah", "7d", "2s"], "pot": 12, "my_stack": 194, "opp_stack": 194,
               "time_left_ms": 0}
        self.assertIn(self.session.handle(req)["card"], req["hole_cards"])

    def test_strategy_exception_gets_legal_fallback(self):
        with patch.object(self.session.bot, "choose_action", side_effect=RuntimeError("test")):
            with contextlib.redirect_stderr(io.StringIO()) as error:
                reply = self.session.handle(request())
        self.assertEqual(reply, {"type": "action", "action": "fold"})
        self.assertIn("RuntimeError", error.getvalue())

    def test_actual_process_replies_only_to_requests_and_exits_on_end(self):
        messages = [init(), new_hand(), {"type": "unknown"}, request(),
                    {"type": "match_end", "reason": "complete"}, request()]
        result = subprocess.run([sys.executable, "-B", str(ROOT / "bot.py")],
                                input="".join(json.dumps(m) + "\n" for m in messages),
                                text=True, capture_output=True, cwd=ROOT, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(replies), 1)
        self.assertTrue(legal_reply(replies[0], request()))


class DiscardStrategyTests(unittest.TestCase):
    def test_worked_examples_and_default_tie_order(self):
        self.assertEqual(set(keep_fast(cards("Qh Jh 4c"), cards("Th 9h 2c"))), set(cards("Qh Jh")))
        self.assertEqual(set(keep_fast(cards("9s 9d Kc"), cards("Th 9h 2c"))), set(cards("9s 9d")))
        self.assertEqual(set(keep_fast(cards("As Ks 2d"), cards("Qs Js Ts"))), set(cards("As Ks")))
        self.assertEqual(lowest_discard(cards("7d 7s Ac")), parse_card("7s"))
        with self.assertRaises(ValueError):
            keep_fast(cards("Qh Jh 4c"), cards("Th 9h 2c 3s 5h"))

    def test_history_to_amounts_and_blinds_are_reconstructed(self):
        history = [{"street": "preflop", "actor": "me", "action": "raise", "amount": 6},
                   {"street": "preflop", "actor": "opp", "action": "call", "amount": 6},
                   {"street": "flop", "actor": "opp", "action": "raise", "amount": 8},
                   {"street": "flop", "actor": "me", "action": "call", "amount": 8}]
        events = decode_history(history, cards("Th 9h 2c"), True)
        self.assertEqual([e.paid for e in events], [5, 4, 8, 8])
        self.assertEqual([e.pot for e in events], [3, 8, 12, 20])
        self.assertEqual([e.facing for e in events], [1, 4, 0, 8])

    def test_preflop_rollouts_choose_from_flop_only(self):
        bot = DiscardBot(seed=89, config=Config(particles=32, samples=32))
        bot.new_hand(1, cards("As Kd 7c"), True)
        seen = []

        def traced(hole, flop):
            self.assertEqual(len(flop), 3)
            seen.append(flop)
            return keep_fast(hole, flop)

        with patch("pokerbot.agent.keep_fast", side_effect=traced):
            rows = bot.sample_equity((), (), time.perf_counter() + 10)
        self.assertEqual(len(rows), 32)
        self.assertEqual(len(seen), 64)

    def test_discarded_cards_never_reappear_in_postdiscard_rollouts(self):
        bot = DiscardBot(seed=17, config=Config(particles=32, samples=32))
        bot.new_hand(1, cards("As Kd 7c"), True)
        bot.reveal_discard(cards("As 7c"), parse_card("Qs"))
        dead = set(cards("Kd Qs"))
        calls = []

        def traced(hand):
            if len(hand) == 7:
                self.assertFalse(dead.intersection(hand))
                self.assertEqual(len(set(hand)), 7)
                calls.append(hand)
            return evaluate(hand)

        with patch("pokerbot.agent.evaluate", side_effect=traced):
            bot.sample_equity(cards("Ah 7d 2s 3c"), (), time.perf_counter() + 10)
        self.assertEqual(len(calls), 64)
        for hand in bot.belief.hands:
            self.assertFalse(set(bot.original + cards("Qs Ah 7d 2s 3c")).intersection(hand))

    def test_conditioned_pairs_do_not_starve_after_public_discard(self):
        original, board, discard = cards("As Kd 7c"), cards("Ah 7d 2s 3c"), parse_card("Qs")
        belief = Belief(original, board, discard, 96, random.Random(33))
        self.assertTrue(belief.update(board, (), 0.25))
        self.assertEqual(len(belief.hands), 96)
        self.assertTrue(all(len(hand) == 2 and discard not in hand for hand in belief.hands))
        self.assertGreater(sum(belief.weights), 0)

    def test_optimized_discard_is_legal_and_uses_common_samples(self):
        bot = DiscardBot(seed=22, config=Config(particles=32, discard_samples=64))
        bot.new_hand(1, cards("As Ks 2d"), True)
        choice = bot.choose_discard(cards("Qs Js Ts"), 30000)
        self.assertEqual(choice, parse_card("2d"))
        self.assertEqual(len(bot.discard_values), 3)
        self.assertTrue(all(0 <= value <= 1 for value in bot.discard_values))


class OrganizerEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = load_engine()

    def test_fast_evaluator_matches_organizer_evaluator(self):
        rng = random.Random(50029)
        for _ in range(1200):
            hand = rng.sample(range(52), 7)
            official = self.engine.best_hand([card_name(c) for c in hand[:2]],
                                             [card_name(c) for c in hand[2:]])
            score = official[0] << 20
            for i, rank in enumerate(official[1:]):
                score |= rank << (16 - i * 4)
            self.assertEqual(evaluate(hand), score)

    def test_official_allin_hand_still_requests_simultaneous_discards(self):
        class Script:
            def __init__(self, name):
                self.name = name
                self.requests, self.messages, self.notices = [], [], 0

            def send(self, msg):
                self.messages.append(msg)

            def begin(self, req):
                self.current = req
                self.requests.append(req)

            def wait_reply(self, deadline):
                req = self.current
                if req["type"] == "action_request":
                    if "raise" in req["legal_actions"]:
                        reply = {"type": "action", "action": "raise", "amount": req["max_raise"]}
                    else:
                        reply = {"type": "action", "action": "call"}
                else:
                    hole = cards(" ".join(req["hole_cards"]))
                    keep = keep_fast(hole, cards(" ".join(req["board"])))
                    reply = {"type": "discard", "card": card_name(next(c for c in hole if c not in keep))}
                return json.dumps(reply), None

        a, b = Script("A"), Script("B")
        match = SimpleNamespace(bots=(a, b), wall_deadline=float("inf"))
        hand = self.engine.Hand(match, 1, 0, (["As", "Ad", "5c"], ["Kh", "Ks", "Qd"]),
                                ["7c", "Kd", "2h", "9s", "Ac"])
        self.assertEqual(hand.play(), [200, -200])
        for bot in (a, b):
            discards = [r for r in bot.requests if r["type"] == "discard_request"]
            self.assertEqual(len(discards), 1)
            self.assertEqual((discards[0]["my_stack"], discards[0]["opp_stack"]), (0, 0))
            self.assertEqual([r["street"] for r in bot.requests if r["type"] == "action_request"], ["preflop"])


if __name__ == "__main__":
    unittest.main()
