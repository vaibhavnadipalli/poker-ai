from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Calls every bet, and checks when there is nothing to call
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet

    if to_call == 0:
        return Action.check()

    return Action.call()  # If the bet is more than we have, this puts us all in
