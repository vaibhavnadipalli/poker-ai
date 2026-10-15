from poker.action import Action
from poker.card import Rank
from poker.game_state import GameState


RANKS = list(Rank)


def myAI(state: GameState) -> Action:
    # Only puts chips in with a pair or two high cards, and bets when it does
    to_call = max(player.chips_bet for player in state.players) - state.my_player.chips_bet

    hole_ranks = [card.rank for card in state.my_player.hole_cards]
    board_ranks = [card.rank for card in state.community_cards]

    has_pair = hole_ranks[0] == hole_ranks[1] or any(rank in board_ranks for rank in hole_ranks)
    high_cards = all(RANKS.index(rank) >= RANKS.index(Rank.TEN) for rank in hole_ranks)

    if has_pair:
        return Action.raise_by(max(1, state.chips_in_pot // 2))

    if high_cards and not board_ranks:
        return Action.call() if to_call > 0 else Action.check()

    return Action.check() if to_call == 0 else Action.fold()
