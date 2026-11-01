from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Raises by the size of the pot every time
    me = state.my_player
    to_call = max(player.chips_bet for player in state.players) - me.chips_bet
    left_after_calling = me.chips_in_stack - to_call
    can_be_called = any(player is not me and not player.has_folded and player.chips_in_stack > 0 for player in state.players)

    if left_after_calling <= 0 or not can_be_called:
        # A raise would only be a call, as calling takes everything we have, or nobody left has chips to call more
        return Action.check() if to_call == 0 else Action.call()

    # The pot after calling, or the smallest raise if that's more, and at most everything we have left, which puts us all in
    return Action.raise_by(min(max(state.chips_in_pot + to_call, state.min_raise), left_after_calling))
