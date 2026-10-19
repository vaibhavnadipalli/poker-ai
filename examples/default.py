from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Checks when there is nothing to call, and folds to any bet. This is what is played for any bot which makes an invalid move.
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet

    if to_call == 0:
        return Action.check()

    return Action.fold()
