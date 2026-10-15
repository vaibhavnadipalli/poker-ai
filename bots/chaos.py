import random

from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Picks something legal at random
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet
    roll = random.random()

    if roll < 0.2:
        return Action.raise_by(random.randint(1, max(1, state.chips_in_pot)))

    if to_call == 0:
        return Action.check()

    return Action.call() if roll < 0.7 else Action.fold()
