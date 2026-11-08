"""Original bounded-sampling policy for the supplied Discard Hold'em rules."""

import math
import random
import time
from dataclasses import dataclass
from itertools import combinations

from .cards import evaluate
from .discard import discard_likelihood, keep_fast, pair_quality, three_card_strength

STREETS = ("preflop", "flop", "turn", "river")


@dataclass(frozen=True)
class Config:
    particles: int = 96
    samples: int = 96
    discard_samples: int = 128
    adapt: bool = True
    discard_signal: bool = False
    optimize_discard: bool = True
    consistent_flop: bool = True
    exact_river: bool = False
    response_tree: bool = False
    preflop_table: bool = True
    river_cfr: bool = False

    def __post_init__(self):
        for value in (self.particles, self.samples, self.discard_samples):
            if type(value) is not int or not 16 <= value <= 1024:
                raise ValueError("sampling counts must be integers in 16..1024")


@dataclass(frozen=True)
class PublicAction:
    street: int
    opponent: bool
    kind: str
    amount: int
    paid: int
    facing: int
    pot: int
    board: tuple


def select_pair(pairs, fast, outcomes):
    """Choose one pair for ALL hidden worlds, never separately per runout."""
    means = [sum(values) / len(values) for values in outcomes]
    base = pairs.index(fast)
    best = base
    for i in range(len(pairs)):
        differences = [a - b for a, b in zip(outcomes[i], outcomes[base])]
        count = len(differences)
        delta = means[i] - means[base]
        variance = sum((d - delta) ** 2 for d in differences) / max(1, count - 1)
        if delta > math.sqrt(variance / count) + 0.015 and means[i] > means[best]:
            best = i
    return best, tuple(means)


def decode_history(history, board, button):
    """Reconstruct chip payments from protocol street-total ('to') amounts."""
    bets = [1, 2] if button else [2, 1]
    pot, street = 3, 0
    output = []
    for item in history:
        index = STREETS.index(item["street"])
        if index != street:
            if index < street:
                raise ValueError("history is out of order")
            street, bets = index, [0, 0]
        actor = int(item["actor"] == "opp")
        kind = item["action"]
        amount = item.get("amount", 0)
        facing = max(0, bets[1 - actor] - bets[actor])
        paid = amount - bets[actor] if kind in ("call", "raise") else 0
        if paid < 0:
            raise ValueError("negative action payment")
        seen = (0, 3, 4, 5)[street]
        output.append(PublicAction(street, bool(actor), kind, amount, paid,
                                   facing, pot, tuple(board[:seen])))
        pot += paid
        if kind in ("call", "raise"):
            bets[actor] = amount
    return tuple(output)


class OpponentModel:
    def __init__(self):
        self.facing, self.folds = [0, 0], [0, 0]
        self.decisions = self.raises = 0

    def observe(self, event):
        if not event.opponent:
            return
        self.decisions += 1
        self.raises += event.kind == "raise"
        context = int(event.street > 0)
        if event.facing:
            self.facing[context] += 1
            self.folds[context] += event.kind == "fold"

    def fold_rate(self, street):
        context = int(street > 0)
        return (self.folds[context] + 6) / (self.facing[context] + 20)

    @property
    def aggression(self):
        return (self.raises + 3) / (self.decisions + 12)


class Belief:
    """Particles are original triples before discard and kept pairs afterwards."""
    def __init__(self, original, board, opponent_discard, count, rng, signal=True,
                 hands=None, calibrated_preflop=False):
        self.original = original
        self.discard = opponent_discard
        self.signal = signal
        blocked = set(original + board)
        if opponent_discard is not None:
            blocked.add(opponent_discard)
        available = [card for card in range(52) if card not in blocked]
        width = 3 if opponent_discard is None else 2
        self.hands = (list(hands) if hands is not None else
                      [tuple(rng.sample(available, width)) for _ in range(count)])
        self.weights = [1.0] * len(self.hands)
        self.calibrated_preflop = calibrated_preflop
        self.enumerated = hands is not None
        self.processed = 0
        self.features = {}
        self.discard_weighted = False

    def feature(self, hand, board):
        key = hand, board
        value = self.features.get(key)
        if value is None:
            if not board:
                triple = hand if len(hand) == 3 else hand + (self.discard,)
                if self.calibrated_preflop:
                    from .preflop import strength
                    value = strength(triple)
                else:
                    value = three_card_strength(triple)
            else:
                triple = hand if len(hand) == 3 else hand + (self.discard,)
                kept = keep_fast(triple, board[:3]) if len(board) == 3 else hand
                value = pair_quality(kept, board)
            self.features[key] = value
        return value

    def update(self, board, events, aggression, flattening=0):
        blocked = set(self.original + board)
        for i, hand in enumerate(self.hands):
            if blocked.intersection(hand):
                self.weights[i] = 0
        if self.discard is not None and not self.discard_weighted:
            if self.signal:
                for i, hand in enumerate(self.hands):
                    self.weights[i] *= discard_likelihood(hand + (self.discard,), hand, board[:3])
            self.discard_weighted = True
        new_events = events[self.processed:] if events is not None else ()
        for event in new_events:
            if not event.opponent or event.kind == "fold":
                continue
            for i, hand in enumerate(self.hands):
                if not self.weights[i]:
                    continue
                strength = self.feature(hand, event.board)
                if event.kind == "raise":
                    size = event.paid / max(1, event.pot)
                    likelihood = 0.06 + aggression * 0.25 + 1.8 * strength ** (2.6 + min(2, size))
                elif event.kind == "call":
                    price = event.facing / max(1, event.pot + event.facing)
                    likelihood = 0.14 + strength ** (1 + price * 3)
                else:
                    likelihood = 1 - strength * 0.30
                self.weights[i] *= (1 - flattening) * likelihood + flattening
        if events is not None:
            self.processed = len(events)
        maximum = max(self.weights)
        if maximum == 0:
            return False
        self.weights = [weight / maximum for weight in self.weights]
        return True

    def sample(self, rng, count):
        return rng.choices(self.hands, weights=self.weights, k=count)


class DiscardBot:
    def __init__(self, seed=20261108, config=None):
        self.config = config or Config()
        self.rng = random.Random(seed)
        self.model = OpponentModel()
        self.total_hands = 200
        self.bank_ms = 30000
        self.reserve_ms = 1500
        self.fallbacks = 0
        self.hand_id = 0
        self.original = self.hole = ()
        self.board = ()
        self.button = False
        self.opponent_discard = None
        self.belief = None
        self.seen_history = 0
        self.last_equity = None
        self.last_samples = 0
        self.discard_values = ()
        self.planned_keep = None
        self.last_cfr_iterations = 0

    def initialize(self, msg):
        self.total_hands = msg["total_hands"]
        self.bank_ms = msg["time_bank_ms"]
        self.reserve_ms = max(750, self.bank_ms * 0.05)

    def new_hand(self, hand_id, hole, button):
        self.hand_id, self.original, self.hole = hand_id, hole, hole
        self.board, self.button = (), button
        self.opponent_discard = None
        self.belief, self.seen_history = None, 0
        self.planned_keep = None
        self.last_cfr_iterations = 0

    def ingest(self, history, board):
        events = decode_history(history, board, self.button)
        if len(events) < self.seen_history:
            raise ValueError("history was shortened")
        for event in events[self.seen_history:]:
            self.model.observe(event)
        self.seen_history = len(events)
        self.board = board
        return events

    def reveal_discard(self, hole, discarded):
        self.hole, self.opponent_discard = hole, discarded
        # Rebuild conditioned on the public discard, avoiding particle starvation.
        self.belief = None

    def allowance(self, time_left_ms, discard=False):
        remaining = max(1, self.total_hands - self.hand_id + 1)
        usable = max(0, time_left_ms - self.reserve_ms) / 1000
        share = usable / (remaining * 5)
        return min(0.06 if discard else 0.035, share * (1.5 if discard else 0.8))

    def prepare_belief(self, board, events):
        exact = self.config.exact_river and len(board) == 5 and self.opponent_discard is not None
        if exact and (self.belief is None or not self.belief.enumerated):
            blocked = set(self.original + board + (self.opponent_discard,))
            hands = list(combinations([c for c in range(52) if c not in blocked], 2))
            self.belief = Belief(self.original, board, self.opponent_discard,
                                 self.config.particles, self.rng, self.config.discard_signal,
                                 hands=hands, calibrated_preflop=self.config.preflop_table)
        if self.belief is None:
            self.belief = Belief(self.original, board, self.opponent_discard,
                                 self.config.particles, self.rng, self.config.discard_signal,
                                 calibrated_preflop=self.config.preflop_table)
        aggressive = self.model.aggression if self.config.adapt else 0.25
        loose = max(0, 0.30 - self.model.fold_rate(1))
        flattening = min(0.65, loose * 1.5 + max(0, aggressive - 0.25) * 1.2) if self.config.adapt else 0
        if not self.belief.update(board, events, aggressive, flattening):
            self.belief = Belief(self.original, board, self.opponent_discard,
                                 self.config.particles, self.rng, self.config.discard_signal,
                                 calibrated_preflop=self.config.preflop_table)
            if not self.belief.update(board, events, aggressive, flattening):
                raise ArithmeticError("opponent belief collapsed")

    def sample_equity(self, board, events, deadline):
        self.prepare_belief(board, events)
        if self.config.exact_river and len(board) == 5 and self.opponent_discard is not None:
            ours = evaluate(self.hole + board)
            total = sum(self.belief.weights)
            rows = []
            for hand, weight in zip(self.belief.hands, self.belief.weights):
                if not weight:
                    continue
                theirs = evaluate(hand + board)
                share = 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0
                rows.append((share, self.belief.feature(hand, board), weight / total))
            self.last_samples = len(rows)
            self.last_equity = sum(share * weight for share, _, weight in rows)
            return rows
        blocked = set(self.original + board)
        if self.opponent_discard is not None:
            blocked.add(self.opponent_discard)
        pool = [card for card in range(52) if card not in blocked]
        opponents = self.belief.sample(self.rng, self.config.samples)
        own_kept = keep_fast(self.original, board[:3]) if len(self.hole) == 3 and board else self.hole
        planning = (self.config.consistent_flop and self.config.optimize_discard
                    and len(board) == 3 and len(self.hole) == 3 and self.planned_keep is None)
        pairs = tuple(combinations(self.original, 2)) if planning else ()
        outcomes = [[] for _ in pairs]
        if self.config.consistent_flop and self.planned_keep is not None:
            own_kept = self.planned_keep
        rows = []
        for i, opponent in enumerate(opponents):
            if i >= 16 and i % 16 == 0 and time.perf_counter() >= deadline:
                break
            extra = self.rng.sample(pool, 5 - len(board))
            while set(extra).intersection(opponent):
                extra = self.rng.sample(pool, 5 - len(board))
            completed = board + tuple(extra)
            # Discards must be selected from the sampled FLOP, before its runout.
            ours = keep_fast(self.original, completed[:3]) if not board else own_kept
            theirs = keep_fast(opponent, completed[:3]) if len(opponent) == 3 else opponent
            a, b = evaluate(ours + completed), evaluate(theirs + completed)
            value = 1.0 if a > b else 0.5 if a == b else 0.0
            if planning:
                for j, pair in enumerate(pairs):
                    score = evaluate(pair + completed)
                    outcomes[j].append(1.0 if score > b else 0.5 if score == b else 0.0)
            feature = self.belief.feature(opponent, board) if board else three_card_strength(opponent)
            rows.append((value, feature))
        if planning:
            selected, self.discard_values = select_pair(pairs, own_kept, outcomes)
            self.planned_keep = pairs[selected]
            rows = [(outcomes[selected][i], row[1]) for i, row in enumerate(rows)]
        self.last_samples = len(rows)
        self.last_equity = sum(row[0] for row in rows) / len(rows)
        return [(outcome, feature, 1 / len(rows)) for outcome, feature in rows]

    @staticmethod
    def fallback(req):
        legal = req["legal_actions"]
        return {"type": "action", "action": "check" if "check" in legal else "fold"}

    @staticmethod
    def raise_to(req, target):
        return {"type": "action", "action": "raise",
                "amount": max(req["min_raise"], min(req["max_raise"], int(target)))}

    def continuation(self, strength, price, street):
        threshold = 0.35 + 0.65 * price + (0.035 if street == 3 else 0)
        prior = 0.08 + 0.90 / (1 + math.exp(9 * (threshold - strength)))
        if not self.config.adapt:
            return prior
        fold = self.model.fold_rate(street)
        shift = math.log((1 - fold) / fold) - math.log(0.70 / 0.30)
        odds = prior / (1 - prior) * math.exp(max(-1.5, min(1.5, shift)))
        return odds / (1 + odds)

    def choose_action(self, req, board, events):
        fallback = self.fallback(req)
        if req["time_left_ms"] <= self.reserve_ms:
            self.fallbacks += 1
            return fallback
        deadline = time.perf_counter() + self.allowance(req["time_left_ms"])
        legal, street = req["legal_actions"], STREETS.index(req["street"])
        if (self.config.river_cfr and street == 3 and req["to_call"] == 0
                and "raise" in legal and req["pot"] >= 12
                and self.opponent_discard is not None
                and not any(e.street == 3 and not e.opponent for e in events)):
            from .river import solve_river
            cfr_deadline = time.perf_counter() + 2 * self.allowance(req["time_left_ms"])
            return solve_river(self, req, board, events, cfr_deadline)
        if self.config.preflop_table and street == 0:
            from .preflop import strength as calibrated_strength
            strength = calibrated_strength(self.original)
        else:
            strength = three_card_strength(self.original)
        if street == 0 and not any(e.kind == "raise" for e in events):
            if self.button:
                if strength < 0.53:
                    return fallback
                if "raise" in legal:
                    return self.raise_to(req, 6)
            elif strength > 0.76 and "raise" in legal:
                return self.raise_to(req, 8)
            return {"type": "action", "action": "call" if "call" in legal else "check"}

        rows = self.sample_equity(board, events, deadline)
        equity = self.last_equity
        price = req["to_call"] / max(1, req["pot"] + req["to_call"])
        if street == 0:
            threshold = max(price + 0.035, 0.36 + 0.02 * math.log2(max(1, req["opp_bet"] / 2)))
            if req["to_call"] and equity < threshold:
                return fallback
            ours = sum(not e.opponent and e.kind == "raise" for e in events)
            if ("raise" in legal and strength > 0.81
                    and equity > (0.65 if ours == 0 else 0.75)):
                return self.raise_to(req, req["opp_bet"] * 3)
            return {"type": "action", "action": "call" if "call" in legal else "check"}

        realization = 1 if street == 3 else (0.94 if self.button else 0.89)
        call_value = equity * realization * (req["pot"] + req["to_call"]) - req["to_call"]
        if req["to_call"]:
            best = {"type": "action", "action": "call"} if call_value > 0 else fallback
            best_value = max(0, call_value)
        else:
            best, best_value = fallback, equity * req["pot"]
            if self.config.response_tree and street == 3 and not self.button:
                from .responses import river_check_value
                best_value = river_check_value(req, rows, self.model.aggression)
        if "raise" not in legal or (req["to_call"] and equity < 0.65):
            return best
        targets = {self.raise_to(req, req["opp_bet"] + max(2, req["pot"] * size))["amount"]
                   for size in (0.5, 1.0)}
        if equity > 0.86 and (street == 3 or req["my_stack"] <= 3 * req["pot"]):
            targets.add(req["max_raise"])
        for target in sorted(targets):
            risk, opponent_call = target - req["my_bet"], target - req["opp_bet"]
            final_pot = req["pot"] + risk + opponent_call
            price = opponent_call / final_pot
            from .responses import raise_value
            value = raise_value(req, target, rows,
                                lambda feature, price: self.continuation(feature, price, street),
                                self.model.aggression, self.config.response_tree)
            if value > best_value + max(0.3, req["pot"] * 0.04):
                best, best_value = self.raise_to(req, target), value
        return best

    def choose_discard(self, board, time_left_ms):
        if self.config.consistent_flop and self.planned_keep is not None:
            return next(card for card in self.original if card not in self.planned_keep)
        pairs = tuple(combinations(self.original, 2))
        fast = keep_fast(self.original, board)
        if not self.config.optimize_discard or time_left_ms <= self.reserve_ms:
            return next(card for card in self.original if card not in fast)
        deadline = time.perf_counter() + self.allowance(time_left_ms, discard=True)
        # The request carries no history; all evidence observed so far is already
        # in the current belief. Unobserved final flop actions are not invented.
        if self.belief is None:
            self.belief = Belief(self.original, board, None, self.config.particles, self.rng)
        if not self.belief.update(board, None, self.model.aggression):
            self.belief = Belief(self.original, board, None, self.config.particles, self.rng)
        opponents = self.belief.sample(self.rng, self.config.discard_samples)
        pool = [card for card in range(52) if card not in self.original + board]
        outcomes = [[] for _ in pairs]
        for i, triple in enumerate(opponents):
            if i >= 16 and i % 16 == 0 and time.perf_counter() >= deadline:
                break
            runout = self.rng.sample(pool, 2)
            while set(runout).intersection(triple):
                runout = self.rng.sample(pool, 2)
            completed = board + tuple(runout)
            opponent = keep_fast(triple, board)
            score = evaluate(opponent + completed)
            for j, pair in enumerate(pairs):
                ours = evaluate(pair + completed)
                outcomes[j].append(1.0 if ours > score else 0.5 if ours == score else 0.0)
        best, self.discard_values = select_pair(pairs, fast, outcomes)
        return next(card for card in self.original if card not in pairs[best])
