from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Puts every chip in, every time
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet
    left_after_calling = state.my_player.chips_in_stack - to_call

    if left_after_calling <= 0:
        return Action.call()  # Calling already puts us all in

    return Action.raise_by(left_after_calling)
