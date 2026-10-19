from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


def myAI(state: GameState) -> Action:
    # Goes all in when it holds an ace, and otherwise checks or folds
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet
    left_after_calling = state.my_player.chips_in_stack - to_call

    if any(card.rank is Rank.ACE for card in state.my_player.hole_cards):
        if left_after_calling <= 0:
            return Action.call()  # Calling already puts us all in

        return Action.raise_by(left_after_calling)

    if to_call == 0:
        return Action.check()

    return Action.fold()
