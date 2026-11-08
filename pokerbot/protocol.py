"""Official Discard Hold'em protocol 1.0; stdout contains requested replies only."""

import json
import sys

from .agent import Config, DiscardBot, STREETS
from .cards import card_name, parse_card
from .discard import lowest_discard

MAX_LINE_BYTES = 65536


def integer(value, minimum=0, maximum=10 ** 12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("invalid integer")
    return value


def card_list(value, count):
    if not isinstance(value, list) or len(value) != count:
        raise ValueError("unexpected card count")
    result = tuple(parse_card(card) for card in value)
    if len(set(result)) != count:
        raise ValueError("duplicate cards")
    return result


def validate_history(history, street):
    if not isinstance(history, list) or len(history) > 64:
        raise ValueError("invalid history")
    previous = 0
    for entry in history:
        if not isinstance(entry, dict) or entry.get("street") not in STREETS:
            raise ValueError("invalid history street")
        current = STREETS.index(entry["street"])
        if not previous <= current <= street:
            raise ValueError("history is out of order")
        previous = current
        if entry.get("actor") not in ("me", "opp"):
            raise ValueError("unknown actor")
        if entry.get("action") not in ("check", "fold", "call", "raise"):
            raise ValueError("unknown action")
        if entry["action"] in ("call", "raise"):
            integer(entry["amount"])


def validate_action_request(req, original):
    if req.get("street") not in STREETS:
        raise ValueError("unknown street")
    street = STREETS.index(req["street"])
    board = card_list(req["board"], (0, 3, 4, 5)[street])
    if set(original).intersection(board):
        raise ValueError("private and public cards overlap")
    for name in ("pot", "my_bet", "opp_bet", "to_call", "my_stack", "opp_stack", "time_left_ms"):
        integer(req[name])
    if req["to_call"] != max(0, req["opp_bet"] - req["my_bet"]):
        raise ValueError("inconsistent call price")
    legal = req["legal_actions"]
    if not isinstance(legal, list) or not legal or len(set(legal)) != len(legal):
        raise ValueError("invalid legal actions")
    expected = {"fold", "call"} if req["to_call"] else {"check"}
    if set(legal) - {"raise"} != expected:
        raise ValueError("legal actions do not match call price")
    raises_left = integer(req["raises_left"], 0, 4)
    if "raise" in legal:
        low, high = integer(req["min_raise"], 1), integer(req["max_raise"], 1)
        if not req["opp_bet"] < low <= high <= req["my_bet"] + req["my_stack"]:
            raise ValueError("invalid raise bounds")
        if not raises_left or req["opp_stack"] == 0:
            raise ValueError("raise is unavailable")
    validate_history(req["history"], street)
    return board


def legal_reply(reply, req):
    if not isinstance(reply, dict) or reply.get("type") != "action":
        return False
    if reply.get("action") not in req["legal_actions"]:
        return False
    if reply["action"] == "raise":
        amount = reply.get("amount")
        return type(amount) is int and req["min_raise"] <= amount <= req["max_raise"]
    return "amount" not in reply


class ProtocolSession:
    def __init__(self, seed=20261108, config=None):
        self.seed, self.config = seed, config or Config()
        self.bot = DiscardBot(seed, self.config)
        self.finished = False
        self.error_count = 0

    def log_failure(self, exc):
        self.error_count += 1
        if self.error_count <= 16:
            print(f"request_failed: {type(exc).__name__}", file=sys.stderr, flush=True)

    def handle(self, msg):
        if not isinstance(msg, dict):
            return None
        kind = msg.get("type")
        if kind == "init":
            integer(msg["total_hands"], 1)
            integer(msg["time_bank_ms"], 1)
            self.bot = DiscardBot(self.seed, self.config)
            self.bot.initialize(msg)
        elif kind == "new_hand":
            hole = card_list(msg["hole_cards"], 3)
            hand_id = integer(msg["hand_id"], 1)
            if msg["seat"] not in ("button", "big_blind"):
                raise ValueError("unknown seat")
            self.bot.new_hand(hand_id, hole, msg["seat"] == "button")
        elif kind == "action_request":
            try:
                if msg["hand_id"] != self.bot.hand_id or not self.bot.original:
                    raise ValueError("missing new_hand")
                board = validate_action_request(msg, self.bot.original)
                events = self.bot.ingest(msg["history"], board)
                reply = self.bot.choose_action(msg, board, events)
                if not legal_reply(reply, msg):
                    raise ValueError("strategy returned an illegal action")
                return reply
            except Exception as exc:
                self.log_failure(exc)
                return self.bot.fallback(msg)
        elif kind == "discard_request":
            hole = ()
            try:
                hole = card_list(msg["hole_cards"], 3)
                board = card_list(msg["board"], 3)
                if set(hole).intersection(board) or hole != self.bot.original:
                    raise ValueError("invalid discard state")
                if msg["hand_id"] != self.bot.hand_id:
                    raise ValueError("wrong discard hand")
                integer(msg["time_left_ms"])
                self.bot.board = board
                discard = self.bot.choose_discard(board, msg["time_left_ms"])
                if discard not in hole:
                    raise ValueError("strategy returned an illegal discard")
                return {"type": "discard", "card": card_name(discard)}
            except Exception as exc:
                self.log_failure(exc)
                available = hole or self.bot.original
                return {"type": "discard", "card": card_name(lowest_discard(available))}
        elif kind == "discard_result":
            hole = card_list(msg["hole_cards"], 2)
            mine, theirs = parse_card(msg["my_discard"]), parse_card(msg["opp_discard"])
            if set(hole + (mine,)) != set(self.bot.original):
                raise ValueError("discard result does not match our cards")
            if theirs in self.bot.original + self.bot.board:
                raise ValueError("opponent discard overlaps known cards")
            self.bot.reveal_discard(hole, theirs)
        elif kind == "hand_result":
            board = card_list(msg["board"], len(msg["board"]))
            if len(board) not in (0, 3, 4, 5):
                raise ValueError("invalid terminal board")
            validate_history(msg["history"], (0, 3, 4, 5).index(len(board)))
            self.bot.ingest(msg["history"], board)
        elif kind == "match_end":
            self.finished = True
        return None


def main():
    session = ProtocolSession()
    stream = sys.stdin.buffer
    while not session.finished:
        line = stream.readline(MAX_LINE_BYTES + 1)
        if not line:
            break
        if len(line) > MAX_LINE_BYTES:
            while line and not line.endswith(b"\n"):
                line = stream.readline(MAX_LINE_BYTES + 1)
            continue
        try:
            message = json.loads(line)
            response = session.handle(message)
        except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
            session.log_failure(exc)
            continue
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
