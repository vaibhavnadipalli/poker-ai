from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


# David Sklansky and Mason Malmuth's eight groups of starting hands, from their book Hold'em Poker for Advanced Players, as
# thepokerbank.com lists them, strongest first. Wikipedia's "Texas hold 'em starting hands" shows them as a chart. A hand ending in "s" has both cards of the same suit, and one without it has two different suits.
GROUPS = [
    {"AA", "AKs", "KK", "QQ", "JJ"},
    {"AK", "AQs", "AJs", "KQs", "TT"},
    {"AQ", "ATs", "KJs", "QJs", "JTs", "99"},
    {"AJ", "KQ", "KTs", "QTs", "J9s", "T9s", "98s", "88"},
    {"A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s", "KJ", "QJ", "JT", "Q9s", "T8s", "97s", "87s", "77", "76s", "66"},
    {"AT", "KT", "QT", "J8s", "86s", "75s", "65s", "55", "54s"},
    {"K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s", "J9", "T9", "98", "64s", "53s", "44", "43s", "33", "22"},
    {"A9", "K9", "Q9", "J8", "J7s", "T8", "96s", "87", "85s", "76", "74s", "65", "54", "42s", "32s"},
]

LETTERS = dict(zip(Rank, "23456789TJQKA"))  # Rank lists the ranks from lowest to highest


def hand(state: GameState) -> str:
    # Our two cards written like the groups, such as "AKs", "AK" or "QQ"
    high, low = sorted(state.my_player.hole_cards, key=lambda card: list(Rank).index(card.rank), reverse=True)
    suited = high.suit is low.suit and high.rank is not low.rank
    return LETTERS[high.rank] + LETTERS[low.rank] + ("s" if suited else "")


def myAI(state: GameState) -> Action:
    # Goes all in with a hand in the top three of Sklansky and Malmuth's eight groups, or any hand with fewer than 10 big blinds, and otherwise checks or folds
    # With fewer than 10 big blinds, waiting lets the blinds eat our chips, so any two cards are worth going all in with
    me = state.my_player
    to_call = max(player.chips_bet for player in state.players) - me.chips_bet
    left_after_calling = me.chips_in_stack - to_call
    can_be_called = any(player is not me and not player.has_folded and player.chips_in_stack > 0 for player in state.players)
    big_blinds = (me.chips_in_stack + me.chips_bet) / state.big_blind

    if not (big_blinds < 10 or any(hand(state) in group for group in GROUPS[:3])):
        return Action.check() if to_call == 0 else Action.fold()

    if left_after_calling <= 0 or not can_be_called:
        # A raise would only be a call, as calling takes everything we have, or nobody left has chips to call more
        return Action.check() if to_call == 0 else Action.call()

    return Action.raise_by(left_after_calling)  # Everything we have left after calling, which puts us all in
