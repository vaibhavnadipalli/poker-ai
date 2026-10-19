from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Raises by one small blind every time it can
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet
    left_after_calling = state.my_player.chips_in_stack - to_call

    if left_after_calling <= 0:
        return Action.call()  # We can only just call, or not even that, so this puts us all in

    return Action.raise_by(min(1 * state.small_blind, left_after_calling))
