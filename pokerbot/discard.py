"""Discard Hold'em hand features. Discard policies see only their hand and flop."""

from itertools import combinations

from .cards import evaluate


def two_card_strength(hole):
    high, low = sorted((card // 4 + 2 for card in hole), reverse=True)
    if high == low:
        return 0.55 + high * 0.027
    return min(0.94, 0.16 + high * 0.027 + low * 0.014
               + 0.055 * (hole[0] % 4 == hole[1] % 4)
               + 0.035 * (high - low <= 2) - 0.025 * (high - low >= 5))


def three_card_strength(hole):
    scores = sorted((two_card_strength(pair) for pair in combinations(hole, 2)), reverse=True)
    # The third card supplies alternatives, not a third card at showdown.
    return min(0.99, scores[0] + 0.045 * max(0, scores[1] - 0.45) / 0.50)


def pair_quality(hole, board):
    """Likelihood/draw feature, not calibrated showdown equity."""
    if not board:
        return two_card_strength(hole)
    score = evaluate(hole + board)
    category, rank = score >> 20, (score >> 16) & 15
    ours = (hole[0] // 4 + 2, hole[1] // 4 + 2)
    public = [card // 4 + 2 for card in board]
    if category == 0:
        quality = 0.12 + max(ours) * 0.009
    elif category == 1:
        if rank not in ours:
            quality = 0.17 + max(ours) * 0.009
        elif rank > max(public):
            quality = 0.79
        elif rank == max(public):
            kicker = max(r for r in ours if r != rank) if ours[0] != ours[1] else rank
            quality = 0.65 + kicker * 0.004
        elif sum(r > rank for r in set(public)) == 1:
            quality = 0.51
        else:
            quality = 0.39
    elif category == 2:
        low_pair = (score >> 12) & 15
        if not any(r in (rank, low_pair) for r in ours):
            quality = 0.31
        elif public.count(rank) >= 2 or public.count(low_pair) >= 2:
            quality = 0.66
        else:
            quality = 0.84
    elif category == 3:
        quality = 0.43 if public.count(rank) == 3 else 0.89
    else:
        quality = (0, 0, 0, 0, 0.92, 0.95, 0.98, 0.995, 1.0)[category]
    if len(board) < 5:
        suits, mask = [0] * 4, 0
        for card in hole + board:
            suits[card % 4] += 1
            mask |= 1 << (card // 4)
        if max(suits) == 4 and any(suits[c % 4] == 4 for c in hole):
            quality += 0.12
        if ((mask & 0x100F).bit_count() == 4
                or any(((mask >> i) & 31).bit_count() == 4 for i in range(9))):
            quality += 0.055
    return min(1.0, quality) + (score & 0xFFFFF) / 0xFFFFF * 0.00001


def keep_fast(hole, flop):
    """Select two cards using the FLOP only, never the turn or river."""
    if len(hole) != 3 or len(flop) != 3:
        raise ValueError("discard selection requires three private and three flop cards")
    return max(combinations(hole, 2), key=lambda pair: pair_quality(pair, flop))


def lowest_discard(hole):
    # Internal suits cdhs map to official default-discard order s,h,d,c.
    return min(hole, key=lambda card: (card // 4, 3 - card % 4))


def discard_likelihood(original, kept, flop):
    """Soft evidence: do not assume all opponents choose an optimal discard."""
    import math
    best = pair_quality(keep_fast(original, flop), flop)
    selected = pair_quality(kept, flop)
    return 0.35 + 0.65 * math.exp(-max(0.0, best - selected) / 0.085)
