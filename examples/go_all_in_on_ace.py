from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Goes all in when it holds an ace, and otherwise checks or folds
    me = state.my_player
    to_call = max(player.chips_bet for player in state.players) - me.chips_bet
    left_after_calling = me.chips_in_stack - to_call
    can_be_called = any(player is not me and not player.has_folded and player.chips_in_stack > 0 for player in state.players)

    if not any(card.rank is Rank.ACE for card in me.hole_cards):
        return Action.check() if to_call == 0 else Action.fold()

    if left_after_calling <= 0 or not can_be_called:
        # A raise would only be a call, as calling takes everything we have, or nobody left has chips to call more
        return Action.check() if to_call == 0 else Action.call()

    return Action.raise_by(left_after_calling)  # Everything we have left after calling, which puts us all in
