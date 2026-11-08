import contextlib
import io
import json
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from pokerbot.game import Action, Engine
from pokerbot.bots import CallingBot
from pokerbot.protocol import MAX_LINE_BYTES, ProtocolSession, parse_observation
from tests.test_strategy import observation

ROOT = Path(__file__).resolve().parents[1]


def raw_observation(obs=None):
    return json.loads(json.dumps(asdict(obs or observation())))


class ProtocolTests(unittest.TestCase):
    def test_valid_observation_roundtrip_and_string_cards(self):
        obs = observation()
        self.assertEqual(parse_observation(raw_observation(obs)), obs)
        raw = raw_observation()
        raw["hole"] = ["As", "Ah"]
        self.assertEqual(parse_observation(raw).hole, obs.hole)

    def test_invalid_inputs(self):
        changes = [
            {"player": 2}, {"player": True}, {"hole": [1, 1]},
            {"hole": [0, 51]}, {"call_cost": 1000}, {"pot": -1},
            {"min_raise_to": None}, {"max_raise_to": 999},
            {"street": 1}, {"stacks": [0, 100]},
            {"history": [{}]}, {"history": [0]},
        ]
        for change in changes:
            raw = raw_observation()
            raw.update(change)
            with self.subTest(change=change), self.assertRaises((ValueError, KeyError)):
                parse_observation(raw)

    def test_reset_rejects_nonfinite_and_invalid_configuration(self):
        session = ProtocolSession()
        for value in (float("nan"), float("inf"), -1, True):
            with self.assertRaises(ValueError):
                session.handle({"type": "reset", "time_bank": value})

    def test_duplicate_requests_are_idempotent(self):
        session = ProtocolSession()
        request = {"type": "act", "observation": raw_observation()}
        first = session.handle(request)
        remaining = session.bot.remaining_seconds
        self.assertEqual(session.handle(request), first)
        self.assertEqual(session.bot.remaining_seconds, remaining)

    def test_exception_and_invalid_action_fall_back_legally(self):
        for value in (RuntimeError("test"), Action("raise", 99999)):
            session = ProtocolSession()
            error = io.StringIO()
            kwargs = {"side_effect": value} if isinstance(value, Exception) else {"return_value": value}
            with patch.object(session.bot, "act", **kwargs), contextlib.redirect_stderr(error):
                result = session.handle({"type": "act", "observation": raw_observation()})
            self.assertEqual(result, {"action": "fold"})
            self.assertIn("decision_failed", error.getvalue())

    def test_external_time_bank_can_only_reduce_budget(self):
        session = ProtocolSession()
        session.handle({"type": "act", "observation": raw_observation(), "remaining_seconds": 0})
        self.assertEqual(session.bot.remaining_seconds, 0)
        self.assertEqual(session.bot.fallbacks, 1)

    def test_changed_private_cards_or_history_are_rejected(self):
        session = ProtocolSession()
        raw = raw_observation()
        session.handle({"type": "act", "observation": raw})
        changed = dict(raw, hole=[48, 49])
        with self.assertRaises(ValueError):
            session.handle({"type": "act", "observation": changed})
        with self.assertRaises(ValueError):
            session.handle({"type": "act", "observation": dict(raw, hand_id=0)})

    def test_full_engine_game_through_adapter(self):
        session = ProtocolSession()

        class Adapter(CallingBot):
            def act(self, obs):
                response = session.handle({"type": "act", "observation": raw_observation(obs)})
                return Action(response["action"], response.get("amount", 0))

        for hand in range(10):
            result = Engine().play((Adapter(), CallingBot()), list(range(52)), hand_id=hand)
            self.assertEqual(sum(result.profits), 0)
            terminal = {"type": "hand_end", "hand_id": hand, "player": 0,
                        "board": result.board, "history": [asdict(e) for e in result.history]}
            terminal = json.loads(json.dumps(terminal))
            session.handle(terminal)
            decisions = session.bot.model.decisions
            session.handle(terminal)
            self.assertEqual(session.bot.model.decisions, decisions)

    def test_terminal_fold_is_observed_once(self):
        from pokerbot.game import Event
        obs = observation(board="", call=1, maximum=100)
        # Use a genuine preflop observation to keep contribution bounds consistent.
        raw = raw_observation(obs)
        session = ProtocolSession()
        session.handle({"type": "act", "observation": raw})
        event = Event(1, 0, "fold", 0, 0, 30, 5, ())
        end = {"type": "hand_end", "hand_id": obs.hand_id, "player": 0,
               "board": [], "history": [asdict(event)]}
        session.handle(end)
        self.assertEqual(session.bot.model.folds[0], 1)

    def test_adapter_matches_direct_bot_with_terminal_notifications(self):
        import random
        from pokerbot.bots import BaselineBot
        from pokerbot.strategy import AdaptiveBot
        session = ProtocolSession()
        direct = AdaptiveBot(seed=0)

        class Adapter(CallingBot):
            def act(self, obs):
                response = session.handle({"type": "act", "observation": raw_observation(obs)})
                return Action(response["action"], response.get("amount", 0))

        rng = random.Random(82134)
        for hand in range(24):
            deck = list(range(52))
            rng.shuffle(deck)
            a = Engine().play((direct, BaselineBot(seed=hand)), deck, button=hand % 2, hand_id=hand)
            b = Engine().play((Adapter(), BaselineBot(seed=hand)), deck, button=hand % 2, hand_id=hand)
            self.assertEqual(a.profits, b.profits)
            session.handle({"type": "hand_end", "hand_id": hand, "player": 0,
                            "board": b.board, "history": [asdict(e) for e in b.history]})
            self.assertEqual(session.bot.model.decisions, direct.model.decisions)
            self.assertEqual(session.bot.model.folds, direct.model.folds)

    def test_process_handles_bad_lines_and_recovers(self):
        lines = [b"not json\n", b"[]\n", b"x" * (MAX_LINE_BYTES + 100) + b"\n",
                 b'{"type":"reset","seed":7}\n',
                 (json.dumps({"type": "act", "observation": raw_observation()}) + "\n").encode()]
        result = subprocess.run([sys.executable, "-B", str(ROOT / "bot.py")],
                                input=b"".join(lines), capture_output=True, cwd=ROOT, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        responses = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(responses), 5)
        self.assertEqual(responses[0], {"error": "invalid_request"})
        self.assertEqual(responses[2], {"error": "request_too_large"})
        self.assertTrue(responses[3]["ready"])
        self.assertIn(responses[4]["action"], ("fold", "call", "raise"))


if __name__ == "__main__":
    unittest.main()
