"""Cards are integers 0..51: rank * 4 + suit; higher scores win."""

from collections import Counter
from itertools import combinations

RANKS = "23456789TJQKA"
SUITS = "cdhs"
CATEGORY_NAMES = (
    "high card", "pair", "two pair", "three of a kind", "straight",
    "flush", "full house", "four of a kind", "straight flush",
)


def parse_card(value: str) -> int:
    if not isinstance(value, str) or len(value) != 2:
        raise ValueError("card must have a rank and suit")
    try:
        return RANKS.index(value[0].upper()) * 4 + SUITS.index(value[1].lower())
    except ValueError:
        raise ValueError("unknown card") from None


def card_name(card: int) -> str:
    if not isinstance(card, int) or isinstance(card, bool) or not 0 <= card < 52:
        raise ValueError("card must be an integer in 0..51")
    return RANKS[card // 4] + SUITS[card % 4]


def _straight_high(mask: int) -> int:
    for high in range(12, 3, -1):
        if mask & (31 << (high - 4)) == 31 << (high - 4):
            return high + 2
    if mask & 0x100F == 0x100F:
        return 5
    return 0


STRAIGHT_HIGH = tuple(_straight_high(mask) for mask in range(8192))


def _top(mask: int, count: int) -> int:
    value = 0
    for _ in range(count):
        rank = mask.bit_length() - 1
        value = (value << 4) | (rank + 2)
        mask ^= 1 << rank
    return value << (4 * (5 - count))


def evaluate(cards) -> int:
    """Fast 5..7-card evaluator. Caller must supply distinct valid cards.

    The upper bits are the category; five rank nibbles break ties. Keeping
    validation at input boundaries avoids repeating it in Monte Carlo loops.
    """
    counts = [0] * 13
    suit_masks = [0] * 4
    suit_counts = [0] * 4
    mask = 0
    for card in cards:
        rank, suit = card >> 2, card & 3
        counts[rank] += 1
        suit_counts[suit] += 1
        suit_masks[suit] |= 1 << rank
        mask |= 1 << rank

    flush_mask = 0
    for suit in range(4):
        if suit_counts[suit] >= 5:
            flush_mask = suit_masks[suit]
            straight = STRAIGHT_HIGH[flush_mask]
            if straight:
                return (8 << 20) | (straight << 16)
            break

    pairs = []
    trips = []
    for rank in range(12, -1, -1):
        count = counts[rank]
        if count == 4:
            kicker = (mask ^ (1 << rank)).bit_length() + 1
            return (7 << 20) | ((rank + 2) << 16) | (kicker << 12)
        if count == 3:
            trips.append(rank)
        elif count == 2:
            pairs.append(rank)

    if trips and (pairs or len(trips) > 1):
        pair = max(pairs + trips[1:])
        return (6 << 20) | ((trips[0] + 2) << 16) | ((pair + 2) << 12)
    if flush_mask:
        return (5 << 20) | _top(flush_mask, 5)
    straight = STRAIGHT_HIGH[mask]
    if straight:
        return (4 << 20) | (straight << 16)
    if trips:
        rank = trips[0]
        kickers = _top(mask ^ (1 << rank), 2) >> 4
        return (3 << 20) | ((rank + 2) << 16) | kickers
    if len(pairs) >= 2:
        high, low = pairs[:2]
        kicker = (mask ^ (1 << high) ^ (1 << low)).bit_length() + 1
        return (2 << 20) | ((high + 2) << 16) | ((low + 2) << 12) | (kicker << 8)
    if pairs:
        rank = pairs[0]
        kickers = _top(mask ^ (1 << rank), 3) >> 4
        return (1 << 20) | ((rank + 2) << 16) | kickers
    return _top(mask, 5)


def reference_evaluate(cards) -> int:
    """Independent, deliberately slow oracle for tests; never used by the bot."""
    if not 5 <= len(cards) <= 7 or len(set(cards)) != len(cards):
        raise ValueError("expected 5..7 distinct cards")
    if any(type(card) is not int or not 0 <= card < 52 for card in cards):
        raise ValueError("invalid card")

    def five(hand):
        ranks = [card // 4 + 2 for card in hand]
        groups = sorted(((n, r) for r, n in Counter(ranks).items()), reverse=True)
        descending = sorted(ranks, reverse=True)
        flush = len({card % 4 for card in hand}) == 1
        unique = sorted(set(ranks))
        straight = 0
        if len(unique) == 5:
            if unique[-1] - unique[0] == 4:
                straight = unique[-1]
            elif unique == [2, 3, 4, 5, 14]:
                straight = 5
        if flush and straight:
            category, order = 8, [straight]
        elif groups[0][0] == 4:
            category, order = 7, [r for _, r in groups]
        elif [n for n, _ in groups] == [3, 2]:
            category, order = 6, [r for _, r in groups]
        elif flush:
            category, order = 5, descending
        elif straight:
            category, order = 4, [straight]
        elif groups[0][0] == 3:
            category, order = 3, [r for _, r in groups]
        elif [n for n, _ in groups] == [2, 2, 1]:
            category, order = 2, [r for _, r in groups]
        elif groups[0][0] == 2:
            category, order = 1, [r for _, r in groups]
        else:
            category, order = 0, descending
        score = category << 20
        for i, rank in enumerate(order):
            score |= rank << (16 - 4 * i)
        return score

    return max(five(hand) for hand in combinations(cards, 5))
