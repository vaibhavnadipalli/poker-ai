from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Raises by the size of the pot when it has the most chips at the table, and otherwise checks or folds
    me = state.my_player
    to_call = max(player.chips_bet for player in state.players) - me.chips_bet
    left_after_calling = me.chips_in_stack - to_call
    biggest_stack = max(player.chips_in_stack + player.chips_bet for player in state.players)

    if me.chips_in_stack + me.chips_bet < biggest_stack:
        return Action.check() if to_call == 0 else Action.fold()

    if left_after_calling <= 0:
        return Action.call()  # We can only just call, or not even that, so this puts us all in

    pot_after_calling = state.chips_in_pot + to_call
    return Action.raise_by(min(max(pot_after_calling, state.min_raise), left_after_calling))
