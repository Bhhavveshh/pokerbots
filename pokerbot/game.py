"""Configurable development engine. No opponent cards enter observations."""

from dataclasses import dataclass
from typing import Optional

from .cards import evaluate


@dataclass(frozen=True)
class GameConfig:
    stack: int = 200
    small_blind: int = 1
    big_blind: int = 2

    def __post_init__(self):
        if any(type(x) is not int for x in (self.stack, self.small_blind, self.big_blind)):
            raise ValueError("chip quantities must be integers")
        if not 0 < self.small_blind <= self.big_blind <= self.stack:
            raise ValueError("expected 0 < small blind <= big blind <= stack")


@dataclass(frozen=True)
class Action:
    kind: str
    amount: int = 0  # Raise TO total contribution on this street.


@dataclass(frozen=True)
class Event:
    player: int
    street: int
    kind: str
    amount: int
    paid: int
    pot_before: int
    call_cost: int
    board: tuple


@dataclass(frozen=True)
class Observation:
    hand_id: int
    player: int
    button: int
    hole: tuple
    board: tuple
    stacks: tuple
    pot: int
    street: int
    contributions: tuple
    call_cost: int
    min_raise_to: Optional[int]
    max_raise_to: Optional[int]
    big_blind: int
    history: tuple = ()

    @property
    def legal_actions(self):
        actions = ["fold", "call"] if self.call_cost else ["check"]
        if self.max_raise_to is not None:
            actions.append("raise")
        return tuple(actions)

    def fallback(self):
        return Action("check" if self.call_cost == 0 else "fold")

    def validate(self, action):
        if not isinstance(action, Action) or action.kind not in self.legal_actions:
            raise ValueError("illegal action")
        if type(action.amount) is not int:
            raise ValueError("action amount must be an integer")
        if action.kind == "raise":
            if not self.min_raise_to <= action.amount <= self.max_raise_to:
                raise ValueError("raise outside legal bounds")
        elif action.amount != 0:
            raise ValueError("only raises carry an amount")


@dataclass(frozen=True)
class HandResult:
    profits: tuple
    board: tuple
    showdown: bool
    revealed_holes: tuple
    history: tuple


class Engine:
    def __init__(self, config=None):
        self.config = config or GameConfig()

    def play(self, bots, deck, button=0, hand_id=0):
        if len(deck) != 52 or set(deck) != set(range(52)):
            raise ValueError("deck must be a permutation of 0..51")
        if button not in (0, 1) or len(bots) != 2:
            raise ValueError("expected two bots and a valid button")
        cfg = self.config
        # Same deck and button are reused with bot seats swapped in duplicate play.
        holes = (tuple(deck[:2]), tuple(deck[2:4]))
        runout = tuple(deck[4:9])
        stacks = [cfg.stack, cfg.stack]
        invested = [0, 0]
        history = []
        for seat, bot in enumerate(bots):
            bot.start_hand(seat, hand_id)

        def pay(seat, amount, contributions):
            amount = min(stacks[seat], amount)
            stacks[seat] -= amount
            invested[seat] += amount
            contributions[seat] += amount
            return amount

        def finish(winner=None, showdown=False, board=()):
            if showdown:
                # Refund uncalled chips before comparing hands.
                difference = invested[0] - invested[1]
                if difference:
                    rich = 0 if difference > 0 else 1
                    stacks[rich] += abs(difference)
                    invested[rich] -= abs(difference)
                scores = [evaluate(holes[p] + tuple(board)) for p in (0, 1)]
                winner = None if scores[0] == scores[1] else int(scores[1] > scores[0])
            pot = sum(invested)
            if winner is None:
                stacks[0] += pot // 2
                stacks[1] += pot // 2
                stacks[1 - button] += pot % 2
            else:
                stacks[winner] += pot
            profits = tuple(stack - cfg.stack for stack in stacks)
            if sum(profits) != 0:
                raise AssertionError("chip conservation failed")
            return HandResult(profits, tuple(board), showdown,
                              holes if showdown else (), tuple(history))

        for street, board_size in enumerate((0, 3, 4, 5)):
            board = runout[:board_size]
            contributions = [0, 0]
            if street == 0:
                pay(button, cfg.small_blind, contributions)
                pay(1 - button, cfg.big_blind, contributions)
            current_bet = max(contributions)
            last_raise = cfg.big_blind
            pending = {p for p in (0, 1) if stacks[p] > 0}
            raise_rights = set(pending)
            actor = button if street == 0 else 1 - button
            while pending:
                if actor not in pending:
                    actor = 1 - actor
                other = 1 - actor
                # No action is necessary once an all-in has been matched.
                if stacks[other] == 0 and contributions[actor] >= current_bet:
                    pending.discard(actor)
                    continue
                call_cost = min(stacks[actor], current_bet - contributions[actor])
                maximum = contributions[actor] + stacks[actor]
                can_raise = actor in raise_rights and stacks[other] > 0 and maximum > current_bet
                obs = Observation(
                    hand_id, actor, button, holes[actor], board, tuple(stacks),
                    sum(invested), street, tuple(contributions), call_cost,
                    min(current_bet + last_raise, maximum) if can_raise else None,
                    maximum if can_raise else None, cfg.big_blind, tuple(history),
                )
                action = bots[actor].act(obs)
                obs.validate(action)
                pending.discard(actor)
                raise_rights.discard(actor)
                paid = 0
                if action.kind == "fold":
                    event = Event(actor, street, "fold", 0, 0, obs.pot, call_cost, board)
                    history.append(event)
                    for bot in bots:
                        bot.observe(event)
                    return finish(other, board=board)
                if action.kind == "call":
                    paid = pay(actor, call_cost, contributions)
                elif action.kind == "raise":
                    increment = action.amount - current_bet
                    paid = pay(actor, action.amount - contributions[actor], contributions)
                    current_bet = action.amount
                    if increment >= last_raise:
                        last_raise = increment
                        raise_rights = {other}
                    if stacks[other] > 0:
                        pending.add(other)
                event = Event(actor, street, action.kind, action.amount, paid,
                              obs.pot, call_cost, board)
                history.append(event)
                for bot in bots:
                    bot.observe(event)
                actor = other
            if min(stacks) == 0:
                return finish(showdown=True, board=runout)
        return finish(showdown=True, board=runout)
