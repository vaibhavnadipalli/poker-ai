from poker.action import Action
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Puts every chip in when its two cards are a pair, and otherwise checks or folds
    card, other_card = state.my_player.hole_cards
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet
    left_after_calling = state.my_player.chips_in_stack - to_call

    if card.rank == other_card.rank:
        if left_after_calling <= 0:
            return Action.call()  # Calling already puts us all in

        return Action.raise_by(left_after_calling)

    if to_call == 0:
        return Action.check()

    return Action.fold()
