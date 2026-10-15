from enum import Enum


class Rank(Enum):
    TWO = "two"
    THREE = "three"
    FOUR = "four"
    FIVE = "five"
    SIX = "six"
    SEVEN = "seven"
    EIGHT = "eight"
    NINE = "nine"
    TEN = "ten"
    JACK = "jack"
    QUEEN = "queen"
    KING = "king"
    ACE = "ace"


class Suit(Enum):
    SPADE = "spade"
    HEART = "heart"
    DIAMOND = "diamond"
    CLUB = "club"


class Card:
    def __init__(self, rank: Rank, suit: Suit):
        self.rank = rank
        self.suit = suit
    
    def __repr__(self):
        return f"Card({self.rank}, {self.suit})"
    
    def __eq__(self, other):
        return self.rank == other.rank and self.suit == other.suit if isinstance(other, Card) else NotImplemented

    def __hash__(self):
        return hash((self.rank, self.suit))
