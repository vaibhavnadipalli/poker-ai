from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


# Phil Hellmuth's six tiers of starting hands, from his book Play Poker Like the Pros, as Wikipedia's "Texas hold 'em starting
# hands" lists them, strongest first. A hand ending in "s" has both cards of the same suit, and one without it has two different suits.
TIERS = [
    {"AA", "KK", "AKs", "QQ", "AK"},
    {"JJ", "TT", "99"},
    {"88", "77", "AQs", "AQ"},
    {"66", "55", "44", "33", "22", "AJs", "ATs", "A9s", "A8s"},
    {"A7s", "A6s", "A5s", "A4s", "A3s", "A2s", "KQs", "KQ"},
    {"QJs", "JTs", "T9s", "98s", "87s", "76s", "65s"},
]

LETTERS = dict(zip(Rank, "23456789TJQKA"))  # Rank lists the ranks from lowest to highest


def hand(state: GameState) -> str:
    # Our two cards written like the tiers, such as "AKs", "AK" or "QQ"
    high, low = sorted(state.my_player.hole_cards, key=lambda card: list(Rank).index(card.rank), reverse=True)
    suited = high.suit is low.suit and high.rank is not low.rank
    return LETTERS[high.rank] + LETTERS[low.rank] + ("s" if suited else "")


def myAI(state: GameState) -> Action:
    # Goes all in with a hand in the top three of Phil Hellmuth's six tiers, or any hand with fewer than 10 big blinds, and otherwise checks or folds
    # With fewer than 10 big blinds, waiting lets the blinds eat our chips, so any two cards are worth going all in with
    me = state.my_player
    to_call = max(player.chips_bet for player in state.players) - me.chips_bet
    left_after_calling = me.chips_in_stack - to_call
    can_be_called = any(player is not me and not player.has_folded and player.chips_in_stack > 0 for player in state.players)
    big_blinds = (me.chips_in_stack + me.chips_bet) / state.big_blind

    if not (big_blinds < 10 or any(hand(state) in tier for tier in TIERS[:3])):
        return Action.check() if to_call == 0 else Action.fold()

    if left_after_calling <= 0 or not can_be_called:
        # A raise would only be a call, as calling takes everything we have, or nobody left has chips to call more
        return Action.check() if to_call == 0 else Action.call()

    return Action.raise_by(left_after_calling)  # Everything we have left after calling, which puts us all in
