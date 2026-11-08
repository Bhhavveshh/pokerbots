"""Bounded response estimates. Hero decisions average over hidden hands first."""

import math


def raise_value(req, target, rows, continuation, aggression=0.25, tree=False):
    """Rows are (showdown share, opponent feature, normalized probability)."""
    pot = req["pot"]
    risk = target - req["my_bet"]
    call = target - req["opp_bet"]
    final = pot + risk + call
    price = call / final
    value = 0.0
    raise_mass = win_mass = 0.0
    can_reraise = tree and req["raises_left"] >= 2 and target < req["max_raise"]
    reraised_to = min(req["max_raise"], max(target + max(2, target - req["opp_bet"]), int(target * 2.5)))
    rate = max(0.02, min(0.40, 0.05 + 1.5 * (aggression - 0.15)))
    for outcome, feature, weight in rows:
        continuing = continuation(feature, price)
        reraising = 0.0
        if can_reraise:
            value_raise = rate / (1 + math.exp(14 * (0.86 - feature)))
            bluff_raise = 0.025 * min(2, aggression / 0.25) * max(0, 0.55 - feature)
            reraising = min(continuing * 0.75, value_raise + bluff_raise)
        value += weight * ((1 - continuing) * pot
                           + (continuing - reraising) * (outcome * final - risk))
        raise_mass += weight * reraising
        win_mass += weight * reraising * outcome
    if raise_mass:
        total_risk = reraised_to - req["my_bet"]
        opponent_paid = reraised_to - req["opp_bet"]
        called_pot = pot + total_risk + opponent_paid
        # ONE call/fold choice for this information set. Maximizing separately
        # in each hidden world would let hero see the opponent's private cards.
        call_value = win_mass * called_pot - raise_mass * total_risk
        fold_value = -raise_mass * risk
        value += max(call_value, fold_value)
    return value


def river_check_value(req, rows, aggression=0.25):
    pot = req["pot"]
    bet = min(req["opp_stack"], max(2, int(pot * 0.75)))
    checked = bet_mass = win_mass = 0.0
    for outcome, feature, weight in rows:
        betting = min(0.95, 0.10 + max(0, aggression - 0.20)
                      + 0.70 / (1 + math.exp(10 * (0.70 - feature))))
        checked += weight * (1 - betting) * outcome * pot
        bet_mass += weight * betting
        win_mass += weight * betting * outcome
    # Again, decide using the conditional range, not the sampled hidden hand.
    return checked + max(0, win_mass * (pot + 2 * bet) - bet_mass * bet)
