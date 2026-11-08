"""Locally authored, seeded opponents for the official runner; not submission code."""

import json
import random
import sys

from .agent import Config
from .cards import card_name, parse_card
from .discard import keep_fast, lowest_discard, pair_quality, three_card_strength
from .protocol import ProtocolSession


class HeuristicOpponent:
    def __init__(self, mode):
        self.mode = mode
        self.rng = random.Random(7919)
        self.hole = ()
        self.finished = False
        self.total_hands = 200
        self.hand_id = 0

    def handle(self, msg):
        kind = msg.get("type")
        if kind == "init":
            self.total_hands = msg["total_hands"]
        elif kind == "new_hand":
            self.hole = tuple(parse_card(c) for c in msg["hole_cards"])
            self.hand_id = msg["hand_id"]
        elif kind == "discard_result":
            self.hole = tuple(parse_card(c) for c in msg["hole_cards"])
        elif kind == "discard_request":
            board = tuple(parse_card(c) for c in msg["board"])
            kept = keep_fast(self.hole, board)
            discard = next(c for c in self.hole if c not in kept)
            return {"type": "discard", "card": card_name(discard)}
        elif kind == "action_request":
            mode = self.mode
            if mode == "switching":
                mode = "calling" if self.hand_id <= self.total_hands // 2 else "tight"
            legal = msg["legal_actions"]
            if mode == "calling":
                return {"type": "action", "action": "check" if "check" in legal else "call"}
            board = tuple(parse_card(c) for c in msg["board"])
            strength = (three_card_strength(self.hole) if not board else
                        pair_quality(keep_fast(self.hole, board) if len(self.hole) == 3 else self.hole, board))
            price = msg["to_call"] / max(1, msg["pot"] + msg["to_call"])
            roll = self.rng.random()
            if mode == "shove":
                if "raise" in legal and roll < 0.3:
                    return {"type": "action", "action": "raise", "amount": msg["max_raise"]}
                action = "check" if "check" in legal else "call" if roll < 0.75 else "fold"
                return {"type": "action", "action": action}
            raise_threshold = 0.78 if mode == "tight" else 0.67
            bluff = mode == "aggressive" and roll < 0.24
            if "raise" in legal and (strength > raise_threshold or bluff):
                amount = msg["opp_bet"] + max(2, int(msg["pot"] * 0.75))
                return {"type": "action", "action": "raise",
                        "amount": max(msg["min_raise"], min(msg["max_raise"], amount))}
            if "check" in legal:
                return {"type": "action", "action": "check"}
            cutoff = (0.69 if not board else price + 0.28) if mode == "tight" else price + 0.13
            return {"type": "action", "action": "call" if strength >= cutoff else "fold"}
        elif kind == "match_end":
            self.finished = True
        return None


def run_opponent(mode):
    if mode in ("reference", "no_signal", "fast_discard"):
        config = Config(adapt=mode != "reference", discard_signal=mode not in ("reference", "no_signal"),
                        optimize_discard=mode not in ("reference", "fast_discard"))
        session = ProtocolSession(seed=7919, config=config)
    else:
        session = HeuristicOpponent(mode)
    for line in sys.stdin:
        message = json.loads(line)
        reply = session.handle(message)
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)
        if session.finished:
            break
