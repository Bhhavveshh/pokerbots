"""Additional locally authored stress opponents; never tournament evidence."""

from dataclasses import replace

from .bots import BaseBot, CallingBot, TightBot
from .game import Action
from .strategy import RangeBot


class UniformEquityBot(RangeBot):
    """Equity/response policy with a uniformly random opponent hand range."""
    def _samples(self, obs, deadline):
        return super()._samples(replace(obs, history=()), deadline)


class ValueBot(RangeBot):
    """Range-aware value policy that assumes every bet gets called."""
    def continuation(self, strength, price, street):
        return 1.0


class ShoveBot(BaseBot):
    def act(self, obs):
        if obs.max_raise_to is not None and self.rng.random() < 0.30:
            return Action("raise", obs.max_raise_to)
        if obs.call_cost:
            return Action("call" if self.rng.random() < 0.60 else "fold")
        return Action("check")


class SwitchingBot(BaseBot):
    """Alternates between a calling station and a tight policy every 100 hands."""
    def __init__(self, seed=0):
        super().__init__(seed)
        self.children = (CallingBot(seed), TightBot(seed + 1))
        self.active = self.children[0]

    def start_hand(self, seat, hand_id):
        super().start_hand(seat, hand_id)
        self.active = self.children[(hand_id // 100) % 2]
        self.active.start_hand(seat, hand_id)

    def act(self, obs):
        return self.active.act(obs)
