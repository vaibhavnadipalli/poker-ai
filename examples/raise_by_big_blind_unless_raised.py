from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Raises by the big blind whenever nobody has bet more than the big blind, and folds to anything bigger
    biggest_bet = max(player.chips_bet for player in state.players)
    to_call = biggest_bet - state.my_player.chips_bet
    left_after_calling = state.my_player.chips_in_stack - to_call

    if biggest_bet > state.big_blind:
        return Action.check() if to_call == 0 else Action.fold()

    if left_after_calling <= 0:
        return Action.call()  # We can only just call, or not even that, so this puts us all in

    return Action.raise_by(min(state.big_blind, left_after_calling))
