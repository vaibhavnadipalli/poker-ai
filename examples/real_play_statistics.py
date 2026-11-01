from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


# Nine tiers of starting hands from statistics based on real play, which rank each hand by how much it won on average in
# real games, as Wikipedia's "Texas hold 'em starting hands" lists them, strongest first. The statistics are PokerRoom.com's.
# A hand ending in "s" has both cards of the same suit, and one without it has two different suits.
TIERS = [
    {"AA", "KK", "QQ", "JJ", "AKs"},
    {"AQs", "TT", "AK", "AJs", "KQs", "99"},
    {"ATs", "AQ", "KJs", "88", "KTs", "QJs"},
    {"A9s", "AJ", "QTs", "KQ", "77", "JTs"},
    {"A8s", "K9s", "AT", "A5s", "A7s"},
    {"KJ", "66", "T9s", "A4s", "Q9s"},
    {"J9s", "QJ", "A6s", "55", "A3s", "K8s", "KT"},
    {"98s", "T8s", "K7s", "A2s"},
    {"87s", "QT", "Q8s", "44", "A9", "J8s", "76s", "JT"},
]

LETTERS = dict(zip(Rank, "23456789TJQKA"))  # Rank lists the ranks from lowest to highest


def hand(state: GameState) -> str:
    # Our two cards written like the tiers, such as "AKs", "AK" or "QQ"
    high, low = sorted(state.my_player.hole_cards, key=lambda card: list(Rank).index(card.rank), reverse=True)
    suited = high.suit is low.suit and high.rank is not low.rank
    return LETTERS[high.rank] + LETTERS[low.rank] + ("s" if suited else "")


def myAI(state: GameState) -> Action:
    # Goes all in with a hand in the top three of the nine tiers from statistics based on real play, or any hand with fewer than 10 big blinds, and otherwise checks or folds
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
