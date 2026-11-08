"""Independent local test policies; share only card parsing/evaluation with the bot.

These do not import its beliefs, continuation model, discard heuristic, preflop
table or action policy. They are test opponents, never submission modules.
"""

import json
import random
import sys
from itertools import combinations

from .cards import card_name, evaluate, parse_card


def retain(hole, flop):
    def value(pair):
        cards = pair + flop
        suits = [sum(c % 4 == s for c in cards) for s in range(4)]
        ranks = {c // 4 for c in cards}
        if 12 in ranks:
            ranks.add(-1)
        straight = max(sum(r in ranks for r in range(start, start + 5)) for start in range(-1, 9))
        draw = (0.8 if max(suits) == 4 else 0) + (0.4 if straight == 4 else 0)
        return evaluate(cards) + int(draw * (1 << 20))
    return max(combinations(hole, 2), key=value)


class EquityPolicy:
    def __init__(self, mode, samples=48):
        if mode not in ("equity", "polar"):
            raise ValueError("unknown independent opponent")
        self.mode, self.samples = mode, samples
        self.rng = random.Random(43117)
        self.hole = self.original = ()
        self.dead = ()
        self.finished = False

    def estimate(self, board):
        available = [c for c in range(52) if c not in self.original + board + self.dead]
        width = 3 if len(self.hole) == 3 else 2
        result = 0
        for _ in range(self.samples):
            drawn = self.rng.sample(available, width + 5 - len(board))
            opponent = tuple(drawn[:width])
            completed = board + tuple(drawn[width:])
            ours = retain(self.hole, completed[:3]) if len(self.hole) == 3 else self.hole
            theirs = retain(opponent, completed[:3]) if width == 3 else opponent
            a, b = evaluate(ours + completed), evaluate(theirs + completed)
            result += 1 if a > b else 0.5 if a == b else 0
        return result / self.samples

    def handle(self, msg):
        kind = msg["type"]
        if kind == "new_hand":
            self.original = self.hole = tuple(parse_card(c) for c in msg["hole_cards"])
            self.dead = ()
        elif kind == "discard_result":
            self.hole = tuple(parse_card(c) for c in msg["hole_cards"])
            self.dead = (parse_card(msg["opp_discard"]),)
        elif kind == "discard_request":
            flop = tuple(parse_card(c) for c in msg["board"])
            kept = retain(self.hole, flop)
            return {"type":"discard", "card":card_name(next(c for c in self.hole if c not in kept))}
        elif kind == "action_request":
            legal = msg["legal_actions"]
            safe = "check" if "check" in legal else "fold"
            if msg["time_left_ms"] < 1500:
                return {"type":"action", "action":safe}
            board = tuple(parse_card(c) for c in msg["board"])
            equity = self.estimate(board)
            price = msg["to_call"] / max(1, msg["pot"] + msg["to_call"])
            roll = self.rng.random()
            polar = self.mode == "polar"
            value_bet = equity > (0.70 if polar else 0.61) + (0.1 if msg["to_call"] else 0)
            bluff = polar and not msg["to_call"] and equity < 0.4 and roll < 0.18
            if "raise" in legal and (value_bet or bluff):
                amount = msg["opp_bet"] + int(msg["pot"] * (1.25 if polar else 0.60))
                return {"type":"action", "action":"raise",
                        "amount":max(msg["min_raise"], min(msg["max_raise"], amount))}
            if "check" in legal:
                return {"type":"action", "action":"check"}
            margin = 0.07 if not board else 0.035
            return {"type":"action", "action":"call" if equity > price + margin else "fold"}
        elif kind == "match_end":
            self.finished = True
        return None


def main(mode):
    policy = EquityPolicy(mode)
    for line in sys.stdin:
        reply = policy.handle(json.loads(line))
        if reply is not None:
            print(json.dumps(reply, separators=(",", ":")), flush=True)
        if policy.finished:
            break
