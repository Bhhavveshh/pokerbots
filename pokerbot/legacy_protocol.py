"""Development JSONL protocol. Replace this adapter when official specs arrive."""

import json
import math
import sys

from .cards import parse_card
from .game import Event, Observation
from .strategy import AdaptiveBot

MAX_LINE_BYTES = 65536


def integer(value, minimum=0, maximum=1000000000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer")
    return value


def pair(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("expected a pair")
    return tuple(integer(item) for item in value)


def cards(value, lengths):
    if not isinstance(value, (list, tuple)) or len(value) not in lengths:
        raise ValueError("unexpected card count")
    result = tuple(parse_card(c) if isinstance(c, str) else integer(c, 0, 51) for c in value)
    if len(set(result)) != len(result):
        raise ValueError("duplicate cards")
    return result


def finite_number(value, minimum=0.0, maximum=3600.0):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("invalid time bank")
    return float(value)


def parse_history(raw_history, board, street):
    if not isinstance(raw_history, list) or len(raw_history) > 256:
        raise ValueError("invalid history")
    history = []
    for raw in raw_history:
        if not isinstance(raw, dict) or raw.get("kind") not in ("check", "call", "raise", "fold"):
            raise ValueError("invalid event")
        event_street = integer(raw["street"], 0, street)
        event_board = cards(raw["board"], ((0, 3, 4, 5)[event_street],))
        if event_board != board[:len(event_board)]:
            raise ValueError("event board differs from current board")
        if history and event_street < history[-1].street:
            raise ValueError("events are out of order")
        event = Event(integer(raw["player"], 0, 1), event_street, raw["kind"],
                      integer(raw["amount"]), integer(raw["paid"]),
                      integer(raw["pot_before"], 1), integer(raw["call_cost"]), event_board)
        if event.kind != "raise" and event.amount != 0:
            raise ValueError("only raises carry amounts")
        if event.kind in ("check", "fold") and event.paid != 0:
            raise ValueError("check and fold cannot pay chips")
        history.append(event)
    return tuple(history)


def parse_observation(data):
    if not isinstance(data, dict):
        raise ValueError("observation must be an object")
    hand_id = integer(data["hand_id"])
    player = integer(data["player"], 0, 1)
    button = integer(data["button"], 0, 1)
    street = integer(data["street"], 0, 3)
    hole = cards(data["hole"], (2,))
    board = cards(data["board"], ((0, 3, 4, 5)[street],))
    if len(set(hole + board)) != len(hole + board):
        raise ValueError("private and public cards overlap")
    stacks = pair(data["stacks"])
    contributions = pair(data["contributions"])
    pot = integer(data["pot"], 1)
    blind = integer(data["big_blind"], 1)
    cost = integer(data["call_cost"])
    if stacks[player] == 0 or sum(contributions) > pot:
        raise ValueError("inconsistent chips")
    expected_cost = min(stacks[player], max(contributions) - contributions[player])
    if cost != expected_cost:
        raise ValueError("call cost does not match contributions")
    minimum, maximum = data["min_raise_to"], data["max_raise_to"]
    if (minimum is None) != (maximum is None):
        raise ValueError("raise bounds must both be set or both be null")
    if maximum is not None:
        minimum, maximum = integer(minimum, 1), integer(maximum, 1)
        if not max(contributions) < minimum <= maximum == contributions[player] + stacks[player]:
            raise ValueError("inconsistent raise bounds")
        if stacks[1 - player] == 0:
            raise ValueError("cannot raise an all-in opponent")
    history = parse_history(data.get("history", []), board, street)
    return Observation(hand_id, player, button, hole, board, stacks, pot, street,
                       contributions, cost, minimum, maximum, blind, tuple(history))


class ProtocolSession:
    def __init__(self):
        self.reset()

    def reset(self, seed=0, time_bank=60.0, expected_hands=1000):
        self.bot = AdaptiveBot(seed=seed, time_bank=time_bank, expected_hands=expected_hands)
        self.previous = None
        self.cached_action = None
        self.events_seen = ()
        self.closed_hand_id = -1
        self.ended_hand = None

    def finish_hand(self, request):
        hand_id = integer(request["hand_id"])
        player = integer(request["player"], 0, 1)
        board = cards(request["board"], (0, 3, 4, 5))
        street = (0, 3, 4, 5).index(len(board))
        history = parse_history(request["history"], board, street)
        signature = (hand_id, player, board, history)
        if hand_id <= self.closed_hand_id:
            if signature == self.ended_hand:
                return {"ok": True}
            raise ValueError("hand already closed")
        previous = self.previous
        if previous is not None and hand_id < previous.hand_id:
            raise ValueError("hand IDs must increase")
        if previous is not None and hand_id == previous.hand_id:
            if player != previous.player or board[:len(previous.board)] != previous.board:
                raise ValueError("terminal state changed")
            if history[:len(self.events_seen)] != self.events_seen:
                raise ValueError("terminal history was rewritten")
        else:
            self.bot.start_hand(player, hand_id)
            self.events_seen = ()
        for event in history[len(self.events_seen):]:
            self.bot.observe(event)
        self.closed_hand_id, self.ended_hand = hand_id, signature
        self.previous, self.cached_action, self.events_seen = None, None, ()
        return {"ok": True}

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError("request must be an object")
        if request.get("type") == "reset":
            seed = integer(request.get("seed", 0))
            bank = finite_number(request.get("time_bank", 60.0))
            hands = integer(request.get("expected_hands", 1000), 1, 1000000)
            self.reset(seed, bank, hands)
            return {"ready": True, "protocol": "development-v1"}
        if request.get("type") == "hand_end":
            return self.finish_hand(request)
        if request.get("type") != "act":
            raise ValueError("unknown message type")
        obs = parse_observation(request["observation"])
        if obs.hand_id <= self.closed_hand_id:
            raise ValueError("hand is already closed")
        external_bank = (finite_number(request["remaining_seconds"])
                         if "remaining_seconds" in request else None)
        previous = self.previous
        new_hand = previous is None or obs.hand_id != previous.hand_id
        if previous is not None:
            if obs.hand_id < previous.hand_id:
                raise ValueError("hand IDs must increase")
            if not new_hand:
                if obs.hole != previous.hole or obs.player != previous.player or obs.button != previous.button:
                    raise ValueError("private state changed within a hand")
                if obs.board[:len(previous.board)] != previous.board:
                    raise ValueError("board changed within a hand")
                if obs.history[:len(self.events_seen)] != self.events_seen:
                    raise ValueError("history was rewritten")
                if obs == previous:
                    if external_bank is not None:
                        self.bot.remaining_seconds = min(self.bot.remaining_seconds, external_bank)
                    return dict(self.cached_action)
        if new_hand:
            self.bot.start_hand(obs.player, obs.hand_id)
            self.events_seen = ()
        for event in obs.history[len(self.events_seen):]:
            self.bot.observe(event)
        self.events_seen = obs.history
        if external_bank is not None:
            self.bot.remaining_seconds = min(self.bot.remaining_seconds, external_bank)
        try:
            action = self.bot.act(obs)
            obs.validate(action)
        except Exception as exc:
            # A valid observation gives us a safe legal fallback at this boundary.
            # Preserve the failure category on stderr, never in protocol stdout.
            print(f"decision_failed: {type(exc).__name__}", file=sys.stderr, flush=True)
            action = obs.fallback()
        response = {"action": action.kind}
        if action.kind == "raise":
            response["amount"] = action.amount
        self.previous, self.cached_action = obs, response
        return dict(response)


def main():
    session = ProtocolSession()
    stream = sys.stdin.buffer
    while True:
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_LINE_BYTES:
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_LINE_BYTES + 1)
            response = {"error": "request_too_large"}
        else:
            try:
                request = json.loads(line)
                response = session.handle(request)
            except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
                response = {"error": "invalid_request"}
        print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
