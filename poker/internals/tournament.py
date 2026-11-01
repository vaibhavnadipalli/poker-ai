from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .engine import AI, Match, Seat
from .rules import Rules


TABLE_SIZE = 8  # The most players who can sit at one table


BONUS_CHIPS = 10  # Added to a player's score for last place, twice for the place above, and so on up to the winner


def score(peak: int, place: int, entrants: int) -> int:
    # A player's score, for keeping a table of results from week to week: their peak chips, the most chips they had at the end
    # of any hand, and a bonus for where they finished: BONUS_CHIPS for last, twice that for the place above, and so on.
    #
    # Most of it is for building a stack. A bot which folds every hand can outlast bots which gamble with each other, but it never
    # wins a pot, so its peak chips stay at about its starting stack and it only gets the bonus for where it finished.
    return peak + BONUS_CHIPS * (entrants + 1 - place)


@dataclass
class Result:
    # Where a player finished. Players who went out say on which hand, and at which table.
    place: int
    name: str
    stack: int
    errors: int
    table: int | None = None
    hand: int | None = None
    peak: int = 0  # The most chips they had at the end of any hand
    score: int = 0


@dataclass
class Exit:
    seat: Seat
    table: int
    hand: int
    started_with: int  # Chips at the start of the hand they went out on, which decides between players who went out on the same hand
    position: int  # Their seat at the table, which decides between those who also started it with the same chips


class Table:
    def __init__(self, number: int, match: Match):
        self.number = number  # Counting from 1
        self.match = match
        self.closed = False
        self.moved_to: list[int] = []  # The tables its players were sent to, once it has closed

    def players(self) -> list[Seat]:
        # The players still in at this table
        return [seat for seat in self.match.seats if seat.stack > 0]

    def hands_played(self) -> int:
        return len(self.match.hands)

    def in_play(self) -> bool:
        # Still open, with hands left to play. It may be down to one player, waiting for players to be moved to it or from it.
        limit = self.match.rules.hands  # 0 means no limit
        return not self.closed and bool(self.players()) and (not limit or self.hands_played() < limit)

    def can_deal(self) -> bool:
        return self.in_play() and not self.match.is_over()


class Tournament:
    # One or more tables of poker. Players are shared out between as few tables as they fit at, and as tables empty
    # the smallest is broken up and its players sent to the others. The tournament is over once one player has every chip,
    # or once no table can deal another hand, because each table has played the most hands which the rules allow.
    #
    # The tables play hand for hand: no table deals its next hand until every other table has finished the one before, and
    # players are only moved once they all have. So hand 5 at one table is played alongside hand 5 at every other, players
    # who go out on the same hand at different tables can be placed fairly, and no table is broken up before the rest have dealt.
    def __init__(self, *, ais: list[tuple[str, AI]], rules: Rules | None = None, seed: int | None = None, table_size: int = TABLE_SIZE):
        if len(ais) < 2:
            raise ValueError(f"Expected at least 2 AIs, but there were {len(ais)}")

        self.rules = rules if rules is not None else Rules()
        self.table_size = table_size
        count = math.ceil(len(ais) / table_size)
        self.tables: list[Table] = []

        for index in range(count):
            # Dealt out in turn like cards, so that the tables are as even as they can be. The first table gets the seed itself,
            # so a single table plays exactly the same hands as a Match would.
            table_seed = seed if seed is None or index == 0 else f"{seed}/{index}"
            self.tables.append(Table(index + 1, Match(ais=ais[index::count], rules=self.rules, seed=table_seed)))

        for table in self.tables:
            # With more than one table, every table shares the same blinds. They all go up together, between hands, as soon as
            # the rules say they should at any table. A single table goes up by itself, exactly as a Match does.
            table.match.shared_blinds = count > 1

        # Every player gets a random id for the whole tournament, so that an AI can tell players apart, and learn how each one
        # plays, without knowing who they are. It comes from a random number generator of its own, so the cards don't change.
        seats = [seat for table in self.tables for seat in table.match.seats]
        ids = random.Random(None if seed is None else f"{seed}/ids").sample(range(1, 1_000_000), len(seats))

        for seat, number in zip(seats, ids):
            seat.id = number

        self.entrants = len(ais)
        self.exits: list[Exit] = []
        self.recorded: set[Seat] = set()

    # ---- Playing

    def play(self):
        # Plays the whole tournament without watching it
        while not self.is_over():
            table = next(table for table in self.tables if self.may_deal(table))
            self.play_hand(table)

    def may_deal(self, table: Table) -> bool:
        # Whether a table can deal its next hand now, rather than waiting for the other tables to catch up with it
        dealing = [other for other in self.tables if other.can_deal()]
        return table in dealing and table.hands_played() == min(other.hands_played() for other in dealing)

    def play_hand(self, table: Table) -> dict:
        # Plays the next hand at a table, and moves players between tables once every table has played it. Returns the hand that was played.
        if not self.may_deal(table):
            raise ValueError(f"Table {table.number} can't deal until the other tables have caught up with it")

        match = table.match
        match.play_hand(table.hands_played() + 1)
        hand = match.hands[-1]
        self.record_exits(table, hand)

        if len({other.hands_played() for other in self.tables if other.in_play()}) <= 1:
            self.rebalance()
            self.raise_blinds()

        return hand

    def raise_blinds(self):
        # Between rounds, every table goes up a level together if any table is due to. Tables with hands left are the ones that count.
        tables = [table for table in self.tables if table.in_play() and table.match.shared_blinds]

        if not any(table.match.blinds_due() for table in tables):
            return

        level = max(table.match.blind_level for table in tables) + 1

        for table in tables:
            match = table.match

            while match.blind_level < level:
                match.raise_blinds()

            match.notes.append(f"the blinds go up to {match.small_blind}/{match.big_blind} at every table")

    def is_over(self) -> bool:
        return len(self.players()) < 2 or not any(table.can_deal() for table in self.tables)

    def players(self) -> list[Seat]:
        return [seat for table in self.tables for seat in table.players()]

    def hands_played(self) -> int:
        return sum(table.hands_played() for table in self.tables)

    # ---- Going out

    def record_exits(self, table: Table, hand: dict):
        # Called straight after the hand, so the seats are still in the order the hand was played in
        for position, (seat, started_with) in enumerate(zip(table.match.seats, hand["frames"][0]["stacks"])):
            if seat.stack == 0 and seat not in self.recorded:
                self.recorded.add(seat)
                self.exits.append(Exit(seat=seat, table=table.number, hand=hand["number"], started_with=started_with, position=position))

    def standings(self) -> list[Result]:
        # Players still in come first, most chips first. Then everyone who went out, the last to go out first. Of players who went
        # out on the same hand, at any table, whoever started that hand with more chips finishes higher, as is usual in a tournament.
        still_in = sorted(self.players(), key=lambda seat: seat.stack, reverse=True)
        # Any exact tie goes to the lower numbered table, then the earlier seat, so the places never depend on which table happened
        # to play the hand first
        gone = sorted(self.exits, key=lambda exit: (exit.hand, exit.started_with, -exit.table, -exit.position), reverse=True)
        results = [Result(place=0, name=seat.name, stack=seat.stack, errors=seat.errors, peak=seat.peak) for seat in still_in]
        results += [Result(place=0, name=exit.seat.name, stack=0, errors=exit.seat.errors, table=exit.table, hand=exit.hand, peak=exit.seat.peak) for exit in gone]

        for place, result in enumerate(results, start=1):
            result.place = place
            result.score = score(result.peak, place, self.entrants)

        return results

    def out(self) -> list[Result]:
        # Everyone who has gone out, in the order they went out, with the places they finished in
        return [result for result in reversed(self.standings()) if result.hand is not None]

    # ---- Moving players

    def rebalance(self):
        # Only tables with hands left take part. A table which has played all its hands keeps its players.
        tables = [table for table in self.tables if table.in_play()]

        if len(tables) < 2:
            return

        # Break up the smallest tables while the players would fit at fewer of them
        while len(tables) > 1 and len(tables) > math.ceil(sum(len(table.players()) for table in tables) / self.table_size):
            closing = min(tables, key=lambda table: (len(table.players()), -table.number))
            tables.remove(closing)

            for seat in list(closing.players()):
                target = min(tables, key=lambda table: (len(table.players()), table.number))
                self.move(seat, closing, target)

                if target.number not in closing.moved_to:
                    closing.moved_to.append(target.number)

            closing.closed = True

        # Then keep the tables within one player of each other, so nobody sits short-handed for long
        while True:
            biggest = max(tables, key=lambda table: (len(table.players()), -table.number))
            smallest = min(tables, key=lambda table: (len(table.players()), table.number))

            if len(biggest.players()) - len(smallest.players()) < 2:
                break

            self.move(self.next_big_blind(biggest), biggest, smallest)

    def next_big_blind(self, table: Table) -> Seat:
        # The player who would pay the big blind next at this table moves, which is the usual way to choose
        match = table.match
        order = [match.seats[(match.button + 1 + index) % len(match.seats)] for index in range(len(match.seats))]
        order = [seat for seat in order if seat.stack > 0]
        return order[min(2, len(order) - 1)]

    def move(self, seat: Seat, source: Table, target: Table):
        source.match.remove(seat)

        # Anyone who has gone out at the table being moved to gives up their seat first, so there is room
        for gone in [other for other in target.match.seats if other.stack == 0]:
            target.match.remove(gone)

        target.match.add(seat)
        source.match.notes.append(f"{seat.name} moves to table {target.number}")
        target.match.notes.append(f"{seat.name} joins from table {source.number}")
