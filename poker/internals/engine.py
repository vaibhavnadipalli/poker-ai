from __future__ import annotations

import random
import signal
import threading
from contextlib import contextmanager
from typing import Callable

from ..action import Action
from ..card import Card, Rank, Suit
from ..game_state import GameState
from .hand import describe, evaluate
from ..player import Blind, MyPlayer, Player
from .rules import Rules
from .sandbox import BotProblem


AI = Callable[[GameState], Action]

RANK_CHARS = dict(zip(Rank, "23456789TJQKA"))
SUIT_CHARS = {Suit.SPADE: "s", Suit.HEART: "h", Suit.DIAMOND: "d", Suit.CLUB: "c"}


def card_code(card: Card) -> str:
    return RANK_CHARS[card.rank] + SUIT_CHARS[card.suit]


class TimeLimitExceeded(BaseException):  # Not an Exception, so that an AI can't swallow it with `except Exception`
    pass


@contextmanager
def time_limit(seconds: float):
    # Only enforceable where SIGALRM exists (not Windows) and only from the main thread
    if not seconds or not hasattr(signal, "setitimer") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def on_alarm(signum, frame):
        raise TimeLimitExceeded()

    previous = signal.signal(signal.SIGALRM, on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)

    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class Seat:
    def __init__(self, *, name: str, ai: AI, stack: int):
        self.name = name
        self.ai = ai
        self.stack = stack
        self.hole_cards: list[Card] = []
        self.blind: Blind | None = None
        self.dealt = False
        self.folded = False
        self.bet = 0  # Chips put in during the current betting round
        self.total_bet = 0  # Chips put in during the current hand
        self.errors = 0
        self.peak = stack  # The most chips this player has had at the end of any hand, which is their score


class Match:
    # No-limit Texas hold'em between the given AIs, played by the given rules. A player with no chips left is out.
    def __init__(self, *, ais: list[tuple[str, AI]], rules: Rules | None = None, seed: int | None = None):
        if len(ais) < 2:
            raise ValueError(f"Expected at least 2 AIs, but there were {len(ais)}")

        self.rules = rules if rules is not None else Rules()
        self.seats = [Seat(name=name, ai=ai, stack=self.rules.stack) for name, ai in ais]
        self.small_blind = self.rules.small_blind
        self.big_blind = self.rules.big_blind
        self.blind_level = 0
        self.hands_at_level = 0
        self.hands_since_cut = 0
        self.orbits_completed = 0
        self.orbits_at_level = 0
        self.orbits_since_cut = 0
        self.buttons_this_orbit: set[Seat] = set()
        self.timeout = self.rules.timeout
        self.ante = 0  # The ante for the current hand
        self.notes: list[str] = []  # Anything to mention at the start of the next hand, such as a player joining the table
        self.shared_blinds = False  # Whether something else, such as a tournament of several tables, decides when the blinds go up

        self.rng = random.Random(seed)
        self.button = self.rng.randrange(len(self.seats))
        self.hands: list[dict] = []

        self.board: list[Card] = []
        self.frames: list[dict] = []
        self.pot = 0
        self.current_bet = 0
        self.min_raise = self.big_blind

    def play(self):
        # Plays until one player has every chip, or until the most hands the rules allow if they set a limit
        number = 1

        while not self.is_over() and (not self.rules.hands or number <= self.rules.hands):
            self.play_hand(number)
            number += 1

    def is_over(self) -> bool:
        return sum(seat.stack > 0 for seat in self.seats) < 2

    def current_ante(self) -> int:
        # The ante in the rules is for the starting blinds, and it goes up with the blinds. It starts from a blind level, or from an orbit.
        rules = self.rules
        started = (rules.ante_from_level and self.blind_level + 1 >= rules.ante_from_level) or (rules.ante_from_orbit and self.orbits_completed >= rules.ante_from_orbit - 1) or not (rules.ante_from_level or rules.ante_from_orbit)
        return int(rules.ante * self.big_blind / rules.big_blind + 0.5) if rules.ante and started else 0

    def blinds_due(self) -> bool:
        # Whether the rules say the blinds go up before the next hand
        rules = self.rules
        return bool((rules.blinds_up_every_orbits and rules.blinds_up_every_orbits <= self.orbits_at_level) or (rules.blinds_up_every_hands and rules.blinds_up_every_hands <= self.hands_at_level))

    def raise_blinds(self):
        rules = self.rules
        self.blind_level += 1
        self.hands_at_level = 0
        self.orbits_at_level = 0
        scale = rules.blind_levels[self.blind_level % len(rules.blind_levels)] / rules.blind_levels[0] * 10 ** (self.blind_level // len(rules.blind_levels))
        self.small_blind, self.big_blind = (int(blind * scale + 0.5) for blind in (rules.small_blind, rules.big_blind))

    def remove(self, seat: Seat):
        # Takes a player away from the table between hands. The button stays with the player who had it, or moves back a seat if it was theirs.
        index = self.seats.index(seat)
        self.seats.pop(index)
        self.buttons_this_orbit.discard(seat)

        if index <= self.button:
            self.button = (self.button - 1) % max(len(self.seats), 1)

    def add(self, seat: Seat):
        # Sits a player down between hands, straight after the player who will be the small blind on the next hand.
        # That makes them the big blind on the next hand, so they can't skip paying the blinds by moving tables.
        seat.dealt = seat.folded = False
        seat.blind = None
        seat.hole_cards = []
        seat.bet = seat.total_bet = 0
        order = [self.seats[(self.button + 1 + index) % len(self.seats)] for index in range(len(self.seats))] if self.seats else []
        order = [other for other in order if other.stack > 0]  # The next button, then the next small blind, and so on

        if not order:
            self.seats.append(seat)
            return

        index = self.seats.index(order[min(1, len(order) - 1)]) + 1
        self.seats.insert(index, seat)

        if index <= self.button:
            self.button += 1

        if self.dealt_after(self.button) is seat:
            # With one or two players left, that seat is straight after the button. The button still has to move on to the
            # player who was going to get it, so it is treated as passing over the new player.
            self.button = index

    def dealt_after(self, index: int) -> Seat | None:
        # The next player after the given seat who has chips, going round the table
        return next((self.seats[(index + step) % len(self.seats)] for step in range(1, len(self.seats) + 1) if self.seats[(index + step) % len(self.seats)].stack > 0), None)

    def play_hand(self, number: int):
        rules = self.rules
        happened = "".join(f", and {note}" for note in self.notes)
        self.notes = []

        if (rules.cut_every_orbits and rules.cut_every_orbits <= self.orbits_since_cut) or (
            rules.cut_every_hands and rules.cut_every_hands <= self.hands_since_cut
        ):
            self.hands_since_cut = 0
            self.orbits_since_cut = 0
            happened += f", and everyone loses {rules.cut_share:.0%} of their chips"

            for seat in self.seats:
                seat.stack -= int(seat.stack * rules.cut_share)  # Rounded down, so that nobody is put out by it

        if not self.shared_blinds and self.blinds_due():
            self.raise_blinds()
            happened += f", and the blinds go up to {self.small_blind}/{self.big_blind}"

        self.hands_at_level += 1
        self.hands_since_cut += 1
        ante = self.ante = self.current_ante()
        total_chips = sum(seat.stack for seat in self.seats)

        for seat in self.seats:
            seat.dealt = seat.stack > 0
            seat.folded = False
            seat.blind = None
            seat.hole_cards = []
            seat.bet = 0
            seat.total_bet = 0

        self.button = self.seats.index(self.dealt_from(self.button + 1)[0])
        dealt = self.dealt_from(self.button + 1)  # Ends with the button

        deck = [Card(rank, suit) for rank in Rank for suit in Suit]
        self.rng.shuffle(deck)

        for seat in dealt:
            seat.hole_cards = [deck.pop(), deck.pop()]

        self.board = []
        self.frames = []
        self.pot = 0
        self.current_bet = 0
        self.min_raise = self.big_blind

        small, big = (dealt[1], dealt[0]) if len(dealt) == 2 else (dealt[0], dealt[1])  # Heads-up, the button is the small blind
        small.blind = Blind.SMALL
        big.blind = Blind.BIG

        hand = {
            "number": number,
            "players": [seat.name for seat in self.seats],
            "button": self.button,
            "small_blind": self.seats.index(small),
            "big_blind": self.seats.index(big),
            "blinds": (self.small_blind, self.big_blind),
            "ante": ante,
            "hole_cards": [[card_code(card) for card in seat.hole_cards] if seat.dealt else None for seat in self.seats],
            "board": self.board,
            "ranks": [None] * len(self.seats),
            "frames": self.frames,
        }

        self.frame("deal", f"Hand {number}: {self.seats[self.button].name} has the button{happened}")

        if ante:
            # An ante goes straight into the pot, and doesn't count towards calling a bet
            for seat in dealt:
                self.put_in(seat, ante)
                seat.bet = 0

            self.frame("ante", f"Everyone pays the ante of {ante}")

        for seat, amount, label in ((small, self.small_blind, "small blind"), (big, self.big_blind, "big blind")):
            paid = self.put_in(seat, amount)

            if paid > 0:  # A player can have nothing left to post, if the ante took their last chips
                self.frame("blind", f"{seat.name} posts the {label} of {paid}", seat=seat, label=f"Blind {paid}")

        self.current_bet = max(small.bet, big.bet)  # Less than the big blind if the blinds are too short of chips to post it

        self.betting_round(self.dealt_from(self.seats.index(big) + 1))

        for street, count in (("Flop", 3), ("Turn", 1), ("River", 1)):
            if len(self.live()) < 2:
                break

            for seat in dealt:
                seat.bet = 0

            self.current_bet = 0
            self.min_raise = self.big_blind

            cards = [deck.pop() for _ in range(count)]
            self.board += cards
            self.frame("street", f"{street}: {' '.join(card_code(card) for card in cards)}")

            self.betting_round(dealt)

        self.settle(dealt, hand)

        hand["board"] = [card_code(card) for card in self.board]

        self.hands.append(hand)

        for seat in dealt:
            seat.peak = max(seat.peak, seat.stack)

            if seat.stack == 0:
                seat.dealt = False
                self.frame("bust", f"{seat.name} is out", seat=seat, label="Out")

        assert self.pot == 0 and sum(seat.stack for seat in self.seats) == total_chips, "Chips were created or destroyed"
        self.buttons_this_orbit.add(self.seats[self.button])

        if all(seat.stack == 0 or seat in self.buttons_this_orbit for seat in self.seats):
            self.orbits_completed += 1
            self.orbits_at_level += 1
            self.orbits_since_cut += 1
            self.buttons_this_orbit.clear()

    def dealt_from(self, start: int) -> list[Seat]:
        # The players in this hand, in the order they act, starting from the given seat
        seats = [self.seats[index % len(self.seats)] for index in range(start, start + len(self.seats))]
        return [seat for seat in seats if seat.dealt]

    def live(self) -> list[Seat]:
        return [seat for seat in self.seats if seat.dealt and not seat.folded]

    def put_in(self, seat: Seat, amount: int) -> int:
        amount = min(amount, seat.stack)
        seat.stack -= amount
        seat.bet += amount
        seat.total_bet += amount
        self.pot += amount
        return amount

    def betting_round(self, order: list[Seat]):
        acted: set[Seat] = set()
        index = 0
        skipped = 0

        while skipped < len(order):
            seat = order[index % len(order)]
            index += 1

            if self.must_act(seat, acted):
                self.act(seat)
                acted.add(seat)
                skipped = 0
            else:
                skipped += 1

        self.return_uncalled()

    def must_act(self, seat: Seat, acted: set[Seat]) -> bool:
        live = self.live()

        if seat.folded or seat.stack == 0 or len(live) < 2:
            return False

        if seat.bet < self.current_bet:
            return True

        if seat in acted:
            return False

        return sum(other.stack > 0 for other in live) > 1  # Otherwise there is nobody left to bet against

    def act(self, seat: Seat):
        to_call = self.current_bet - seat.bet
        action, problem = self.ask(seat)

        if problem is None and action.kind is Action.Kind.CHECK and to_call > 0:
            problem = "checked when there was a bet to call"

        if problem is None:
            kind = action.kind
        else:
            # The same as defaultAI in myAI.py
            seat.errors += 1
            kind = Action.Kind.CHECK if to_call == 0 else Action.Kind.FOLD

        if kind is Action.Kind.RAISE:
            most = seat.stack - to_call
            can_be_called = any(other.stack > 0 for other in self.live() if other is not seat)

            if most <= 0 or not can_be_called:
                kind = Action.Kind.CALL

        if kind is Action.Kind.CALL and to_call == 0:
            kind = Action.Kind.CHECK

        if kind is Action.Kind.FOLD:
            seat.folded = True
            text, label = "folds", "Fold"

        elif kind is Action.Kind.CHECK:
            text, label = "checks", "Check"

        elif kind is Action.Kind.CALL:
            paid = self.put_in(seat, to_call)
            text, label = f"calls {paid}", f"Call {paid}"

        else:
            # A raise is by `amount` on top of the bet being called.
            amount = min(action.amount, most)
            if most < self.min_raise:
                amount = most
            else:
                amount = max(amount, self.min_raise)

            opening = self.current_bet == 0
            self.put_in(seat, to_call + amount)
            self.current_bet = seat.bet
            self.min_raise = max(self.min_raise, amount)
            text, label = (f"bets {seat.bet}", f"Bet {seat.bet}") if opening else (f"raises to {seat.bet}", f"Raise {seat.bet}")

        if seat.stack == 0 and kind in (Action.Kind.CALL, Action.Kind.RAISE):
            text += " and is all in"

        self.frame(kind.value, f"{seat.name} {text}", seat=seat, label=label, problem=problem)

    def ask(self, seat: Seat) -> tuple[Action | None, str | None]:
        state = self.state_for(seat)

        try:
            with time_limit(self.timeout):
                action = seat.ai(state)

        except TimeLimitExceeded:
            return None, f"took longer than {self.timeout:g}s"

        except BotProblem as e:  # A bot in a container of its own, which went wrong in there
            return None, str(e)

        except Exception as e:
            return None, f"raised {type(e).__name__}: {e}"[:200]

        if not isinstance(action, Action):
            return None, f"returned {action!r:.150} instead of an Action"

        return action, None

    def state_for(self, seat: Seat) -> GameState:
        # Everything is built fresh, so that an AI can't change the game by changing what it is given
        my_player = MyPlayer(blind=seat.blind, chips_in_stack=seat.stack, chips_bet=seat.bet, hole_cards=set(seat.hole_cards))
        players = [my_player if other is seat else Player(blind=other.blind, has_folded=other.folded, chips_in_stack=other.stack, chips_bet=other.bet) for other in self.seats if other.dealt]

        return GameState(my_player=my_player, players=players, chips_in_pot=self.pot, community_cards=set(self.board), small_blind=self.small_blind, big_blind=self.big_blind, min_raise=self.min_raise, ante=self.ante)

    def return_uncalled(self):
        # If nobody matched the biggest bet, the unmatched part goes back
        dealt = [seat for seat in self.seats if seat.dealt]
        top = max(dealt, key=lambda seat: seat.total_bet)
        excess = top.total_bet - max(seat.total_bet for seat in dealt if seat is not top)

        if excess > 0 and not top.folded:
            top.stack += excess
            top.bet -= min(excess, top.bet)  # Any more than their bet is part of their ante
            top.total_bet -= excess
            self.pot -= excess
            self.frame("return", f"{top.name} gets {excess} back, as nobody called it", seat=top, label=f"{excess} back")

    def settle(self, dealt: list[Seat], hand: dict):
        live = self.live()

        for seat in dealt:
            seat.bet = 0

        if len(live) == 1:
            self.award(live, self.pot, f"{live[0].name} wins {self.pot}")
            return

        scores = {seat: evaluate(seat.hole_cards + self.board) for seat in live}

        for seat in live:
            hand["ranks"][self.seats.index(seat)] = describe(scores[seat])

        self.frame("showdown", "Showdown")
        pots = self.pots(dealt)

        for number, (amount, eligible) in enumerate(pots):
            best = max(scores[seat] for seat in eligible)
            winners = [seat for seat in dealt if seat in eligible and scores[seat] == best]  # Any odd chips go to the first players after the button

            names = " and ".join(seat.name for seat in winners)
            verb = "wins" if len(winners) == 1 else "split"
            pot_name = "" if len(pots) == 1 else "the main pot of " if number == 0 else "the side pot of "
            self.award(winners, amount, f"{names} {verb} {pot_name}{amount} ({describe(best).lower()})")

    def award(self, winners: list[Seat], amount: int, text: str):
        share, extra = divmod(amount, len(winners))

        for index, seat in enumerate(winners):
            seat.stack += share + (index < extra)

        self.pot -= amount
        self.frame("win", text, winners=winners)

    def pots(self, dealt: list[Seat]) -> list[tuple[int, list[Seat]]]:
        # Splits the pot into a main pot and side pots, each with the players who can win it
        pots: list[list] = []
        previous = 0

        for level in sorted({seat.total_bet for seat in dealt if seat.total_bet > 0}):
            amount = sum(min(seat.total_bet, level) - min(seat.total_bet, previous) for seat in dealt)
            eligible = [seat for seat in dealt if not seat.folded and seat.total_bet >= level]
            previous = level

            if pots and (not eligible or eligible == pots[-1][1]):
                pots[-1][0] += amount
            else:
                pots.append([amount, eligible])

        return [(amount, eligible) for amount, eligible in pots]

    def frame(self, kind: str, text: str, *, seat: Seat | None = None, winners: list[Seat] = (), label: str | None = None, problem: str | None = None):
        # A snapshot of the table after each thing that happens, for the visualiser
        self.frames.append({
            "kind": kind,
            "text": text,
            "seat": self.seats.index(seat) if seat is not None else None,
            "winners": [self.seats.index(winner) for winner in winners],
            "label": label,
            "problem": problem,
            "board": len(self.board),
            "pot": self.pot,
            "stacks": [other.stack for other in self.seats],
            "bets": [other.bet for other in self.seats],
            "status": ["out" if not other.dealt else "folded" if other.folded else "all in" if other.stack == 0 else "in" for other in self.seats],
        })
