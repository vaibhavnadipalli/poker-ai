from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Never folds and never raises
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet

    return Action.call() if to_call > 0 else Action.check()
