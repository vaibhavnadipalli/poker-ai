from __future__ import annotations
from enum import Enum

from .card import Card


class Blind(Enum):
    SMALL = "small"
    BIG = "big"


class Player:
    def __init__(self, *, blind: Blind | None = None, has_folded: bool = False, chips_in_stack: int = 0, chips_bet: int = 0, id: int | None = None):
        self.id = id  # The same for this player all tournament, even at another table, and a different random number in every tournament
        self.blind = blind
        self.has_folded = has_folded
        self.chips_in_stack = chips_in_stack
        self.chips_bet = chips_bet

    def __repr__(self):
        return f"Player(id={self.id}, blind={self.blind}, has_folded={self.has_folded}, chips_in_stack={self.chips_in_stack}, chips_bet={self.chips_bet})"

    def __eq__(self, other):
        if not isinstance(other, Player):
            return NotImplemented

        if isinstance(other, MyPlayer):
            return False

        if self.id != other.id:
            return False

        if self.blind != other.blind:
            return False

        if self.has_folded != other.has_folded:
            return False

        if self.chips_in_stack != other.chips_in_stack:
            return False

        if self.chips_bet != other.chips_bet:
            return False

        return True

    def __hash__(self):
        return hash((self.id, self.blind, self.has_folded, self.chips_in_stack, self.chips_bet))


class MyPlayer(Player):
    def __init__(self, *, blind: Blind | None = None, chips_in_stack: int, chips_bet: int = 0, hole_cards: set[Card], id: int | None = None):
        super().__init__(blind=blind, has_folded=False, chips_in_stack=chips_in_stack, chips_bet=chips_bet, id=id)
        self.hole_cards = hole_cards

    def __repr__(self):
        return f"MyPlayer(id={self.id}, blind={self.blind}, chips_in_stack={self.chips_in_stack}, chips_bet={self.chips_bet}, hole_cards={self.hole_cards})"

    def __eq__(self, other):
        if not isinstance(other, Player):
            return NotImplemented

        if not isinstance(other, MyPlayer):
            return False

        if self.id != other.id:
            return False

        if self.blind != other.blind:
            return False

        if self.has_folded != other.has_folded:
            return False

        if self.chips_in_stack != other.chips_in_stack:
            return False

        if self.chips_bet != other.chips_bet:
            return False

        if self.hole_cards != other.hole_cards:
            return False

        return True

    def __hash__(self):
        return hash((self.id, self.blind, self.has_folded, self.chips_in_stack, self.chips_bet, frozenset(self.hole_cards)))
