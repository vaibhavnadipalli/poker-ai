import importlib.util
import json
import random
from pathlib import Path

from poker.action import Action
from poker.card import Card, Rank, Suit
from poker.engine import Match
from poker.game_state import GameState
from poker.player import Blind, MyPlayer, Player

from myAI import myAI

# The bots folder isn't part of the installed package, so the random bot is loaded from its file like the poker command does
chaos_path = Path(__file__).resolve().parent.parent / "bots" / "chaos.py"
chaos_spec = importlib.util.spec_from_file_location("chaos", chaos_path)
chaos = importlib.util.module_from_spec(chaos_spec)
chaos_spec.loader.exec_module(chaos)
randomAI = chaos.myAI

# Bots are scored against each other in tournaments, so the score on a push is only a rough guide.
# A bot which returns an Action on a range of sample states gets WORKING_SCORE, and then up to the rest for its win rate in heads-up matches against the random bot.
NUM_STATES = 1000
WORKING_SCORE = 10

NUM_MATCHES = 100
MATCH_SCORE = 90


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


def check_states() -> list[str]:
    # Returns a description of each sample state on which myAI doesn't return an Action
    rng = random.Random(0)
    failures = []

    for i in range(NUM_STATES):
        state = sample_state(rng)

        try:
            result = myAI(state)
        except Exception as e:
            failures.append(f"state {i}: raised {type(e).__name__}: {e}")
            continue

        if not isinstance(result, Action):
            failures.append(f"state {i}: returned {result!r} instead of an Action")

    return failures


def play_matches() -> tuple[float, int]:
    # Plays heads-up matches against the random bot, and returns the share of matches won and the number of bad actions
    wins = 0.0
    errors = 0

    for number in range(NUM_MATCHES):
        random.seed(number)  # For AIs which use the random module, including the random bot
        ais = [("myAI", myAI), ("random", randomAI)]
        match = Match(ais=ais if number % 2 == 0 else ais[::-1], rules=None, seed=number)  # Seats swap every match
        match.play()

        standings = match.standings()
        leaders = [seat for seat in standings if seat.stack == standings[0].stack]
        me = next(seat for seat in match.seats if seat.name == "myAI")

        if me in leaders:
            wins += 1 / len(leaders)

        errors += me.errors

    return wins / NUM_MATCHES, errors


failures = check_states()

for failure in failures[:10]:
    print(failure)

success_rate = 100 * (NUM_STATES - len(failures)) / NUM_STATES

if failures:
    score = 0
    win_rate = 0.0
    errors = 0
else:
    win_rate, errors = play_matches()
    score = round(WORKING_SCORE + MATCH_SCORE * win_rate)

print(f"Won {win_rate:.0%} of {NUM_MATCHES} matches against the random bot with {errors} bad actions")

details = json.dumps({"states": NUM_STATES, "failures": len(failures), "examples": failures[:10], "matches": NUM_MATCHES, "win_rate": win_rate, "bad_actions": errors})

with open("score.txt", "w") as f:
    f.write(f"score={score}\nsuccess_rate={success_rate:g}\nwin_rate={100 * win_rate:g}\ndetails={details}\n")
