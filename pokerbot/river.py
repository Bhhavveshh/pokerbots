"""Public-range construction for the experimental river CFR policy."""

import bisect
import random
from dataclasses import replace
from itertools import combinations

from .cards import evaluate
from .cfr import CFR, OneBetGame


def public_catalog(board, discards, count=128):
    """A deterministic PUBLIC sample; never condition this on hero's kept cards."""
    known = tuple(board) + tuple(sorted(discards))
    seed = 17
    for card in known:
        seed = seed * 53 + card + 1
    available = [c for c in range(52) if c not in known]
    return random.Random(seed).sample(list(combinations(available, 2)), count)


def bucket_model(hands, scores, own_weights, other_weights, buckets=4):
    """Exact joint mass/equity ON THE SAMPLED CATALOG, excluding card overlaps."""
    ordered = sorted(scores)
    boundaries = sorted(set(ordered[len(ordered) * k // buckets] for k in range(1, buckets)))
    types = [bisect.bisect_right(boundaries, score) for score in scores]
    n = len(boundaries) + 1
    joint = [[0.0] * n for _ in range(n)]
    wins = [[0.0] * n for _ in range(n)]
    for a, hand_a in enumerate(hands):
        i = types[a]
        for b, hand_b in enumerate(hands):
            if hand_a[0] in hand_b or hand_a[1] in hand_b:
                continue
            j = types[b]
            mass = own_weights[a] * other_weights[b]
            joint[i][j] += mass
            wins[i][j] += mass * (1 if scores[a] > scores[b] else 0.5 if scores[a] == scores[b] else 0)
    equity = [[wins[i][j] / joint[i][j] if joint[i][j] else 0.5
               for j in range(n)] for i in range(n)]
    return joint, equity, boundaries


def solve_river(bot, req, board, events, deadline):
    # Both inferred ranges use exactly the same PUBLIC information. Actual hero
    # cards select the output bucket only AFTER solving the whole-range game.
    from .agent import Belief
    own_discard = next(c for c in bot.original if c not in bot.hole)
    discards = own_discard, bot.opponent_discard
    hands = public_catalog(board, discards)
    scores = [evaluate(hand + board) for hand in hands]
    beliefs = []
    for actor, discarded in enumerate(discards):
        belief = Belief(discards, board, discarded, len(hands), random.Random(0),
                        signal=bot.config.discard_signal, hands=hands,
                        calibrated_preflop=bot.config.preflop_table)
        history = tuple(replace(e, opponent=not e.opponent) for e in events) if actor == 0 else events
        aggression = bot.model.aggression if actor == 1 and bot.config.adapt else 0.25
        if not belief.update(board, history, aggression):
            raise ValueError("public river range has zero mass")
        beliefs.append(belief)
    joint, equity, boundaries = bucket_model(hands, scores, beliefs[0].weights, beliefs[1].weights)
    amount = bot.raise_to(req, round(req["pot"] * 0.75))["amount"]
    game = OneBetGame(joint, equity, req["pot"], amount, opponent_after_check=not bot.button)
    solver = CFR(game)
    policy = solver.train(256, deadline)
    bucket = bisect.bisect_right(boundaries, evaluate(bot.hole + board))
    bot.last_cfr_iterations = solver.iterations
    if bot.rng.random() < policy[""][bucket][1]:
        return bot.raise_to(req, amount)
    return {"type": "action", "action": "check"}
