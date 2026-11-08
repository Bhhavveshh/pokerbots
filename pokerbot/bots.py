"""Transparent baseline opponents, also used for regression tournaments."""

import random

from .cards import evaluate
from .game import Action


def preflop_strength(hole):
    high, low = sorted((card // 4 + 2 for card in hole), reverse=True)
    if high == low:
        return 0.52 + high * 0.031
    suited = hole[0] % 4 == hole[1] % 4
    gap = high - low
    return min(0.90, 0.15 + high * 0.027 + low * 0.014
               + 0.055 * suited + 0.035 * (gap <= 2) - 0.025 * (gap >= 5))


def raise_to(obs, target):
    if obs.max_raise_to is None:
        return Action("call" if obs.call_cost else "check")
    return Action("raise", max(obs.min_raise_to, min(obs.max_raise_to, int(target))))


class BaseBot:
    def __init__(self, seed=0):
        self.rng = random.Random(seed)
        self.seat = 0

    def start_hand(self, seat, hand_id):
        self.seat = seat

    def observe(self, event):
        pass


class CallingBot(BaseBot):
    def act(self, obs):
        return Action("call" if obs.call_cost else "check")


class FoldingBot(BaseBot):
    def act(self, obs):
        return obs.fallback()


class RandomBot(BaseBot):
    def act(self, obs):
        kind = self.rng.choice(obs.legal_actions)
        if kind == "raise":
            return raise_to(obs, obs.contributions[obs.player] + obs.call_cost
                            + max(obs.big_blind, obs.pot * self.rng.choice((0.33, 0.75, 1.5))))
        return Action(kind)


class BaselineBot(BaseBot):
    """Phase 1 heuristic; intentionally simple, not an equilibrium strategy."""
    threshold = 0.52
    aggression = 0.0

    def act(self, obs):
        if obs.street == 0:
            strength = preflop_strength(obs.hole)
            if obs.call_cost:
                price = obs.call_cost / (obs.pot + obs.call_cost)
                facing_raise = any(e.kind == "raise" for e in obs.history)
                cutoff = self.threshold + (0.10 if facing_raise else 0)
                cutoff += min(0.18, price * 0.20)
                if strength < cutoff:
                    return Action("fold")
            if strength > 0.79 and obs.max_raise_to is not None:
                return raise_to(obs, max(3 * obs.big_blind,
                                        max(obs.contributions) + obs.pot))
            return Action("call" if obs.call_cost else "check")

        category = evaluate(obs.hole + obs.board) >> 20
        # This baseline knows hand category but does not model opponent ranges.
        strength = (0.18, 0.49, 0.72, 0.81, 0.90, 0.94, 0.98, 0.995, 1.0)[category]
        if obs.call_cost:
            price = obs.call_cost / (obs.pot + obs.call_cost)
            if strength < price + 0.22 - self.aggression:
                return Action("fold")
        if obs.max_raise_to is not None and (strength > 0.70 or self.rng.random() < self.aggression):
            return raise_to(obs, max(obs.contributions) + max(obs.big_blind, obs.pot * 0.65))
        return Action("call" if obs.call_cost else "check")


class TightBot(BaselineBot):
    threshold = 0.68


class AggressiveBot(BaselineBot):
    threshold = 0.39
    aggression = 0.23


BOT_TYPES = {
    "baseline": BaselineBot,
    "calling": CallingBot,
    "folding": FoldingBot,
    "random": RandomBot,
    "tight": TightBot,
    "aggressive": AggressiveBot,
}


def register_strategies():
    # Lazy registration avoids a circular import with the common bot helpers.
    from .strategy import AdaptiveBot, RangeBot
    from .opponents import ShoveBot, SwitchingBot, UniformEquityBot, ValueBot
    BOT_TYPES["range"] = RangeBot
    BOT_TYPES.update(adaptive=AdaptiveBot, equity=UniformEquityBot, value=ValueBot,
                     shove=ShoveBot, switching=SwitchingBot)
