from __future__ import annotations

from collections import Counter

from .card import Card, Rank


RANK_VALUES = {rank: value for value, rank in enumerate(Rank, start=2)}

CATEGORIES = ["High card", "Pair", "Two pair", "Three of a kind", "Straight", "Flush", "Full house", "Four of a kind", "Straight flush"]


def straight_high(values: set[int]) -> int | None:
    if 14 in values:
        values = values | {1}  # The ace also plays low, for A-2-3-4-5

    for high in range(14, 4, -1):
        if all(value in values for value in range(high - 4, high + 1)):
            return high

    return None


def evaluate(cards: list[Card]) -> tuple[int, ...]:
    # Scores the best five card hand that can be made from five or more cards. A higher score is a better hand.
    values = sorted((RANK_VALUES[card.rank] for card in cards), reverse=True)

    suits = Counter(card.suit for card in cards)
    flush_suit = next((suit for suit, count in suits.items() if count >= 5), None)
    flush = sorted((RANK_VALUES[card.rank] for card in cards if card.suit == flush_suit), reverse=True)

    if flush:
        high = straight_high(set(flush))

        if high is not None:
            return (8, high)

    counts = Counter(values)
    quads = sorted((value for value in counts if counts[value] == 4), reverse=True)
    trips = sorted((value for value in counts if counts[value] == 3), reverse=True)
    pairs = sorted((value for value in counts if counts[value] == 2), reverse=True)

    if quads:
        return (7, quads[0], max(value for value in values if value != quads[0]))

    if trips and (len(trips) > 1 or pairs):
        return (6, trips[0], max(trips[1:] + pairs))

    if flush:
        return (5, *flush[:5])

    high = straight_high(set(values))

    if high is not None:
        return (4, high)

    if trips:
        return (3, trips[0], *[value for value in values if value != trips[0]][:2])

    if len(pairs) >= 2:
        return (2, pairs[0], pairs[1], max(value for value in values if value not in pairs[:2]))

    if pairs:
        return (1, pairs[0], *[value for value in values if value != pairs[0]][:3])

    return (0, *values[:5])


def describe(score: tuple[int, ...]) -> str:
    return "Royal flush" if score == (8, 14) else CATEGORIES[score[0]]
