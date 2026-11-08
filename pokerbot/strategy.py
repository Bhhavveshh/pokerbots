"""Bounded particle ranges and response-aware equity decisions.

This is an original heuristic policy, not a solved equilibrium. Particle beliefs
and the opponent response model are deliberately small enough for CPU play.
"""

import math
import time
from dataclasses import dataclass

from .bots import BaseBot, preflop_strength, raise_to
from .cards import evaluate
from .game import Action


@dataclass(frozen=True)
class StrategyConfig:
    particles: int = 160
    samples: int = 128
    decision_seconds: float = 0.025
    open_threshold: float = 0.43

    def __post_init__(self):
        if type(self.particles) is not int or not 16 <= self.particles <= 2048:
            raise ValueError("particles must be in 16..2048")
        if type(self.samples) is not int or not 16 <= self.samples <= 4096:
            raise ValueError("samples must be in 16..4096")
        if not math.isfinite(self.decision_seconds) or not 0 <= self.decision_seconds <= 1:
            raise ValueError("decision seconds must be in 0..1")
        if not math.isfinite(self.open_threshold) or not 0 <= self.open_threshold <= 1:
            raise ValueError("open threshold must be in 0..1")


def made_strength(hole, board):
    """Cheap range-likelihood feature, NOT an equity estimate."""
    if not board:
        return preflop_strength(hole)
    score = evaluate(hole + board)
    category = score >> 20
    rank = (score >> 16) & 15
    hole_ranks = [c // 4 + 2 for c in hole]
    board_ranks = [c // 4 + 2 for c in board]
    if category == 0:
        strength = 0.12 + max(hole_ranks) * 0.009
    elif category == 1:
        if rank not in hole_ranks:
            strength = 0.17 + max(hole_ranks) * 0.009
        elif rank > max(board_ranks):
            strength = 0.79
        elif rank == max(board_ranks):
            strength = 0.65 + min(hole_ranks) * 0.004
        elif rank >= sorted(set(board_ranks), reverse=True)[min(1, len(set(board_ranks)) - 1)]:
            strength = 0.51
        else:
            strength = 0.39
    elif category == 2:
        low_pair = (score >> 12) & 15
        if not any(r in (rank, low_pair) for r in hole_ranks):
            strength = 0.31
        elif board_ranks.count(rank) >= 2 or board_ranks.count(low_pair) >= 2:
            strength = 0.65
        else:
            strength = 0.83
    elif category == 3:
        strength = 0.43 if board_ranks.count(rank) == 3 else 0.88
    else:
        strength = (0, 0, 0, 0, 0.91, 0.95, 0.98, 0.995, 1.0)[category]
    if len(board) < 5:
        suits = [0] * 4
        mask = 0
        for card in hole + board:
            suits[card % 4] += 1
            mask |= 1 << (card // 4)
        if max(suits) == 4 and any(suits[c % 4] == 4 for c in hole):
            strength += 0.10
        # A four-card straight window is only a draw feature, not a made hand.
        if ((mask & 0x100F).bit_count() == 4
                or any(((mask >> i) & 31).bit_count() == 4 for i in range(9))):
            strength += 0.045
    return min(0.999, strength)


def action_likelihood(strength, event, aggression=0.25):
    if event.kind == "raise":
        size = event.paid / max(1, event.pot_before)
        exponent = 2.5 + min(2.0, size)
        # Preserve some bluff probability; never eliminate plausible hands.
        return 0.06 + aggression * 0.20 + 1.8 * strength ** exponent
    if event.kind == "call":
        price = event.call_cost / max(1, event.pot_before + event.call_cost)
        return 0.13 + strength ** (1.0 + price * 3)
    if event.kind == "check":
        return 1.0 - strength * 0.35
    return 1.0


class ParticleRange:
    def __init__(self, hole, board, count, rng):
        blocked = set(hole + board)
        available = [c for c in range(52) if c not in blocked]
        self.hands = [tuple(rng.sample(available, 2)) for _ in range(count)]
        self.weights = [1.0] * count
        self.processed = 0
        self.strengths = {}

    def strength(self, hand, board):
        key = (hand, board)
        value = self.strengths.get(key)
        if value is None:
            value = made_strength(hand, board)
            self.strengths[key] = value
        return value

    def update(self, obs, aggression=0.25, flattening=0.0):
        blocked = set(obs.hole + obs.board)
        for i, hand in enumerate(self.hands):
            if hand[0] in blocked or hand[1] in blocked:
                self.weights[i] = 0.0
        for event in obs.history[self.processed:]:
            if event.player == obs.player:
                continue
            for i, hand in enumerate(self.hands):
                if self.weights[i]:
                    strength = self.strength(hand, event.board)
                    likelihood = action_likelihood(strength, event, aggression)
                    self.weights[i] *= (1 - flattening) * likelihood + flattening
        self.processed = len(obs.history)
        maximum = max(self.weights)
        if maximum == 0:
            return False
        self.weights = [weight / maximum for weight in self.weights]
        return True

    def sample(self, rng, count):
        return rng.choices(self.hands, weights=self.weights, k=count)


class RangeBot(BaseBot):
    def __init__(self, seed=0, config=None):
        super().__init__(seed)
        self.config = config or StrategyConfig()
        self.range = None
        self.last_equity = None
        self.last_samples = 0

    def start_hand(self, seat, hand_id):
        super().start_hand(seat, hand_id)
        self.range = None

    def opponent_aggression(self):
        return 0.25

    def range_flattening(self):
        return 0.0

    def decision_allowance(self):
        return self.config.decision_seconds

    def continuation(self, strength, price, street):
        threshold = 0.34 + 0.65 * price
        if street == 3:
            threshold += 0.035
        return 0.08 + 0.90 / (1.0 + math.exp(9.0 * (threshold - strength)))

    def _samples(self, obs, deadline):
        if self.range is None:
            self.range = ParticleRange(obs.hole, obs.board, self.config.particles, self.rng)
        if not self.range.update(obs, self.opponent_aggression(), self.range_flattening()):
            # Finite particles can all be blocked by a new board. Rebuild from
            # currently legal hands and replay public evidence, never hidden cards.
            self.range = ParticleRange(obs.hole, obs.board, self.config.particles, self.rng)
            if not self.range.update(obs, self.opponent_aggression(), self.range_flattening()):
                raise ArithmeticError("range weights collapsed")
        count = self.config.samples
        opponent_hands = self.range.sample(self.rng, count)
        blocked = set(obs.hole + obs.board)
        available = [c for c in range(52) if c not in blocked]
        missing = 5 - len(obs.board)
        rows = []
        for i, hand in enumerate(opponent_hands):
            # Time checks in batches avoid paying for a clock read per sample.
            if i >= 16 and i % 16 == 0 and time.perf_counter() >= deadline:
                break
            if missing:
                runout = self.rng.sample(available, missing)
                while hand[0] in runout or hand[1] in runout:
                    runout = self.rng.sample(available, missing)
                board = obs.board + tuple(runout)
            else:
                board = obs.board
            ours = evaluate(obs.hole + board)
            theirs = evaluate(hand + board)
            outcome = 1.0 if ours > theirs else 0.5 if ours == theirs else 0.0
            rows.append((outcome, self.range.strength(hand, obs.board)))
        self.last_samples = len(rows)
        self.last_equity = sum(row[0] for row in rows) / len(rows)
        return rows

    def _preflop(self, obs, equity):
        strength = preflop_strength(obs.hole)
        raises = [event for event in obs.history if event.street == 0 and event.kind == "raise"]
        if not raises:
            if obs.player == obs.button:
                if strength < self.config.open_threshold:
                    return obs.fallback()
                return raise_to(obs, 2.5 * obs.big_blind)
            if strength > 0.69:
                return raise_to(obs, 3.5 * obs.big_blind)
            return Action("check")

        price = obs.call_cost / max(1, obs.pot + obs.call_cost)
        facing_size = max(obs.contributions) / obs.big_blind
        threshold = max(price + 0.035, 0.34 + 0.025 * math.log2(max(1, facing_size)))
        if obs.call_cost and equity < threshold:
            return Action("fold")
        our_raises = sum(event.player == obs.player for event in raises)
        if obs.max_raise_to is not None and strength > 0.77 and equity > (0.66 if our_raises == 0 else 0.75):
            return raise_to(obs, max(obs.contributions) * 3)
        return Action("call" if obs.call_cost else "check")

    def act(self, obs):
        deadline = time.perf_counter() + self.decision_allowance()
        # No equity work is needed to select an unopened preflop action.
        if obs.street == 0 and not any(e.kind == "raise" for e in obs.history):
            return self._preflop(obs, 0.5)
        rows = self._samples(obs, deadline)
        equity = self.last_equity
        if obs.street == 0:
            return self._preflop(obs, equity)

        realization = 1.0 if obs.street == 3 else (0.93 if obs.player == obs.button else 0.87)
        call_ev = equity * realization * (obs.pot + obs.call_cost) - obs.call_cost
        if obs.call_cost:
            best = Action("call") if call_ev > 0 else Action("fold")
            best_ev = max(0.0, call_ev)
        else:
            best, best_ev = Action("check"), equity * obs.pot
        if obs.max_raise_to is None:
            return best

        current = max(obs.contributions)
        # Restrict re-raises to plausible value hands; no endless bluff wars.
        if obs.call_cost and equity < 0.64:
            return best
        targets = {raise_to(obs, current + max(obs.big_blind, obs.pot * fraction)).amount
                   for fraction in (0.5, 1.0)}
        for target in sorted(targets):
            # Uncalled chips are refunded; value only the amount at risk.
            opponent = 1 - obs.player
            effective_to = min(target, obs.contributions[opponent] + obs.stacks[opponent])
            risk = effective_to - obs.contributions[obs.player]
            opponent_call = max(0, effective_to - obs.contributions[opponent])
            final_pot = obs.pot + risk + opponent_call
            price = opponent_call / max(1, final_pot)
            value = 0.0
            for outcome, strength in rows:
                continuation = self.continuation(strength, price, obs.street)
                value += ((1 - continuation) * obs.pot
                          + continuation * (outcome * final_pot - risk))
            value /= len(rows)
            # Avoid changing actions on a tiny, noisy simulation advantage.
            margin = max(obs.big_blind * 0.15, obs.pot * 0.035)
            if value > best_ev + margin:
                best, best_ev = Action("raise", target), value
        return best


class OpponentModel:
    """Beta-style shrinkage; separate preflop and postflop response contexts."""
    def __init__(self):
        self.facing = [0, 0]
        self.folds = [0, 0]
        self.decisions = 0
        self.raises = 0

    def observe(self, event):
        self.decisions += 1
        self.raises += event.kind == "raise"
        context = int(event.street > 0)
        if event.call_cost > 0:
            self.facing[context] += 1
            self.folds[context] += event.kind == "fold"

    def fold_rate(self, street):
        context = int(street > 0)
        return (self.folds[context] + 6.0) / (self.facing[context] + 20.0)

    @property
    def aggression(self):
        return (self.raises + 3.0) / (self.decisions + 12.0)


class AdaptiveBot(RangeBot):
    def __init__(self, seed=0, config=None, time_bank=60.0, expected_hands=1000):
        if not math.isfinite(time_bank) or time_bank < 0:
            raise ValueError("time bank must be finite and nonnegative")
        if type(expected_hands) is not int or expected_hands < 1:
            raise ValueError("expected hands must be a positive integer")
        super().__init__(seed, config)
        self.model = OpponentModel()
        self.remaining_seconds = time_bank
        self.reserve_seconds = min(5.0, time_bank * 0.15)
        self.expected_hands = expected_hands
        self.hands_seen = 0
        self.fallbacks = 0

    def start_hand(self, seat, hand_id):
        super().start_hand(seat, hand_id)
        self.hands_seen += 1

    def observe(self, event):
        if event.player != self.seat:
            self.model.observe(event)

    def opponent_aggression(self):
        return self.model.aggression

    def range_flattening(self):
        loose_calls = max(0.0, 0.30 - self.model.fold_rate(1))
        excess_aggression = max(0.0, self.model.aggression - 0.25)
        return min(0.65, loose_calls * 1.5 + excess_aggression * 1.2)

    def decision_allowance(self):
        remaining_hands = max(1, self.expected_hands - self.hands_seen)
        available = max(0.0, self.remaining_seconds - self.reserve_seconds)
        return min(self.config.decision_seconds, available / (remaining_hands * 5))

    def continuation(self, strength, price, street):
        prior = super().continuation(strength, price, street)
        fold_rate = self.model.fold_rate(street)
        shift = math.log((1 - fold_rate) / fold_rate) - math.log(0.70 / 0.30)
        # Capped adjustment keeps hand strength relevant even after many samples.
        shift = max(-1.6, min(1.6, shift))
        odds = prior / (1 - prior) * math.exp(shift)
        return odds / (1 + odds)

    def act(self, obs):
        start = time.perf_counter()
        try:
            if self.remaining_seconds <= self.reserve_seconds:
                self.fallbacks += 1
                return obs.fallback()
            return super().act(obs)
        finally:
            self.remaining_seconds = max(0.0, self.remaining_seconds - (time.perf_counter() - start))
