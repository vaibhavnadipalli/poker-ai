from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Calls any bet when it is the small blind or the big blind, and otherwise checks or folds
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet

    if to_call == 0:
        return Action.check()

    if state.my_player.blind is not None:
        return Action.call()  # If the bet is more than we have, this puts us all in

    return Action.fold()
