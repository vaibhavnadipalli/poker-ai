from __future__ import annotations

import json
import random
from pathlib import Path

from ..action import Action
from ..card import Card, Rank, Suit
from ..game_state import GameState
from ..player import Blind, MyPlayer, Player
from .engine import AI, TimeLimitExceeded, time_limit
from .rules import Rules


# The score on a push is only for passing the tests: a bot which returns an Action, in time, on every one of the sample
# states gets PASSING_SCORE, and otherwise it gets 0. Every other point on the leaderboard comes from the weekly tournaments.
# Scores from before this were 10, and up to 90 more for beating a random bot, so a passing bot is never outscored by an old one.
NUM_STATES = 1000
PASSING_SCORE = 100


def sample_state(rng: random.Random) -> GameState:
    deck = [Card(rank, suit) for rank in Rank for suit in Suit]
    rng.shuffle(deck)

    hole_cards = {deck.pop(), deck.pop()}
    community_cards = {deck.pop() for _ in range(rng.choice([0, 3, 4, 5]))}

    blinds = [Blind.SMALL, Blind.BIG] + [None] * rng.randint(0, 4)
    rng.shuffle(blinds)

    my_player = MyPlayer(blind=blinds[0], chips_in_stack=rng.randint(1, 1000), chips_bet=rng.choice([0, rng.randint(1, 100)]), hole_cards=hole_cards)
    others = [Player(blind=blind, has_folded=rng.random() < 0.25, chips_in_stack=rng.randint(0, 1000), chips_bet=rng.choice([0, rng.randint(1, 100)])) for blind in blinds[1:]]

    players = [my_player] + others
    rng.shuffle(players)

    chips_in_pot = sum(player.chips_bet for player in players) + rng.choice([0, rng.randint(1, 500)])
    big_blind = rng.choice([2, 3, 4, 6, 8, 10, 15, 20])

    return GameState(my_player=my_player, players=players, chips_in_pot=chips_in_pot, community_cards=community_cards, small_blind=big_blind // 2, big_blind=big_blind, ante=rng.choice([0, big_blind]))


def check_states(ai: AI) -> list[str]:
    # Returns a description of each sample state on which the AI doesn't return an Action in time.
    # It gets as long for each one as it does for an action in a game.
    rng = random.Random(0)
    timeout = Rules().timeout
    failures = []

    for number in range(NUM_STATES):
        state = sample_state(rng)

        try:
            with time_limit(timeout):
                result = ai(state)

        except TimeLimitExceeded:
            failures.append(f"state {number}: took longer than {timeout:g}s")
            continue

        except Exception as e:
            failures.append(f"state {number}: raised {type(e).__name__}: {e}"[:200])
            continue

        if not isinstance(result, Action):
            failures.append(f"state {number}: returned {result!r:.150} instead of an Action")

    return failures


def score(ai: AI, output: str | Path = "score.txt") -> int:
    # Scores an AI as the competition does when it is pushed, and writes the result to a file with a line for each of
    # score, success_rate and details, which the WarwickAI/competitions action passes on to GitHub
    failures = check_states(ai)

    for failure in failures[:10]:
        print(failure)

    success_rate = 100 * (NUM_STATES - len(failures)) / NUM_STATES
    total = PASSING_SCORE if not failures else 0

    print(f"Returned an Action on {success_rate:g}% of {NUM_STATES} sample states, so the score is {total}")

    details = json.dumps({"states": NUM_STATES, "failures": len(failures), "examples": failures[:10]})  # json.dumps keeps it on one line, as GitHub needs
    Path(output).write_text(f"score={total}\nsuccess_rate={success_rate:g}\ndetails={details}\n", encoding="utf-8")
    return total
