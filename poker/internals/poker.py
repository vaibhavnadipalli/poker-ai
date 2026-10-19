from __future__ import annotations

import argparse
import csv
import datetime
import importlib.util
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from .engine import AI
from .rules import Rules
from .sandbox import IMAGE, Sandbox
from .score import score as score_ai
from .tournament import TABLE_SIZE, Tournament


STARTING_PATH = list(sys.path)  # The module search path from before any bot is loaded, for the windows to start with


def load_ais(specs: list[str], least: int = 2, taken: list[str] = ()) -> list[tuple[str, AI]]:
    # Each spec is a path to a python file with a myAI function, optionally written as NAME=PATH. Names in taken are already used.
    ais = []

    for index, spec in enumerate(specs):
        name, _, path = spec.rpartition("=")
        path = Path(path)
        name = name or path.stem

        if not path.is_file():
            raise SystemExit(f"poker: there is no file at {path}")

        if str(path.parent.resolve()) not in sys.path:
            sys.path.append(str(path.parent.resolve()))  # So that an AI can import files which are next to it

        module_spec = importlib.util.spec_from_file_location(f"poker_ai_{index}", path)

        if module_spec is None:
            raise SystemExit(f"poker: {path} is not a python file")

        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)

        if not callable(getattr(module, "myAI", None)):
            raise SystemExit(f"poker: {path} doesn't have a myAI function")

        used = [*taken, *(other for other, _ in ais)]
        base = name
        number = 2

        while name in used:
            name = f"{base} {number}"
            number += 1

        ais.append((name, module.myAI))

    if len(ais) < least:
        raise SystemExit(f"poker: expected at least {least} AIs, but there were {len(ais)}")

    return ais


@dataclass
class Team:
    # Where a bot came from, so that its result can be recorded against the team's submission on the website
    repo: str
    commit: str


def load_snapshots(folder: str) -> tuple[list[tuple[str, Path]], dict[str, Team]]:
    # Reads the folder which the website's db/download-snapshots.ts makes: a manifest.csv, and a folder for each team's repo
    # at the commit which was picked. Returns each team's name and its myAI.py, and which team each name is.
    # Nothing is loaded, as their code is only ever run in a container unless --no-sandbox says otherwise.
    folder = Path(folder)
    manifest = folder / "manifest.csv"

    if not manifest.is_file():
        raise SystemExit(f"poker: there is no manifest.csv in {folder}. Make the folder with the website's db/download-snapshots.ts")

    with manifest.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    # Teams are shown by who owns their repo, as many repos keep the template's name
    owners = [row["repo"].split("/")[0] for row in rows]
    bots, teams = [], {}

    for row, owner in zip(rows, owners):
        path = folder / row["folder"] / "myAI.py" if row["folder"] else None

        if path is None or not path.is_file():
            print(f"poker: skipping {row['repo']}, as there is no myAI.py in its snapshot", file=sys.stderr)
            continue

        if float(row["score"] or 0) <= 0:
            print(f"poker: skipping {row['repo']}, as none of its bots has passed the tests", file=sys.stderr)
            continue

        name = owner if owners.count(owner) == 1 else row["repo"]
        bots.append((name, path))
        teams[name] = Team(repo=row["repo"], commit=row["commit"])

    return bots, teams


def write_results(path: str, tournament: Tournament, teams: dict[str, Team], seed: int | None):
    # Writes everyone's result, for the website's db/record-tournament.ts to add to the leaderboard. Players who aren't one
    # of the teams, such as example bots added to make up the numbers, are listed without a repo and aren't recorded.
    complete = tournament.is_over()  # False if it was stopped early, such as by closing a window

    results = {
        "playedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "complete": complete,
        "hands": max(table.hands_played() for table in tournament.tables),
        "players": [
            {
                "name": result.name,
                "repo": teams[result.name].repo if result.name in teams else None,
                "commit": teams[result.name].commit if result.name in teams else None,
                "place": result.place,
                "peakChips": result.peak,
                "score": result.score,
            }
            for result in tournament.standings()
        ],
    }

    Path(path).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"\nResults written to {path}" + ("" if complete else ", but the tournament was stopped before it finished"))


def parse_blinds(text: str) -> tuple[int, int]:
    try:
        small, big = (int(part) for part in text.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected blinds like 10/20, but got {text}")

    if not 0 < small <= big:
        raise argparse.ArgumentTypeError(f"expected 0 < small blind <= big blind, but got {text}")

    return small, big


def positive(text: str) -> int:
    value = int(text)

    if value <= 0:
        raise argparse.ArgumentTypeError(f"expected a number greater than 0, but got {text}")

    return value


def whole(text: str) -> int:
    value = int(text)

    if value < 0:
        raise argparse.ArgumentTypeError(f"expected a whole number of at least 0, but got {text}")

    return value


def load_rules(args: argparse.Namespace) -> Rules:
    # The rules come from poker/internals/rules.yaml or the file given with --rules, and then the command line can change a few of them
    try:
        rules = Rules(args.rules)

        if args.hands is not None:
            rules.hands = args.hands

        if args.stack is not None:
            rules.stack = args.stack

        if args.blinds is not None:
            rules.small_blind, rules.big_blind = args.blinds

        if args.timeout is not None:
            rules.timeout = args.timeout

        rules.check()

    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as e:
        raise SystemExit(f"poker: the rules can't be used: {e}")

    return rules


def new_tournament(args: argparse.Namespace, ais: list[tuple[str, AI]], rules: Rules) -> Tournament:
    if args.seed is not None:
        random.seed(args.seed)  # For AIs which use the random module

    return Tournament(ais=ais, rules=rules, seed=args.seed)


def print_standings(tournament: Tournament):
    tables = len(tournament.tables)
    print(f"Played {tournament.hands_played()} hands" + (f" across {tables} tables" if tables > 1 else ""))

    print(f"    {'Player':<20} {'Chips':>8} {'Peak chips':>11} {'Score':>6}")

    for result in tournament.standings():
        notes = []

        if result.hand is not None:
            notes.append(f"out on hand {result.hand}" + (f" at table {result.table}" if tables > 1 else ""))

        if result.errors:
            notes.append(f"{result.errors} bad actions")

        print(f"{result.place:>2}. {result.name:<20} {result.stack:>8} {result.peak:>11} {result.score:>6}" + (f"  ({', '.join(notes)})" if notes else ""))

    out = tournament.out()

    if out:
        print()
        print("Went out")

        for number, result in enumerate(out, start=1):
            where = f"hand {result.hand}" + (f" at table {result.table}" if tables > 1 else "")
            print(f"{number:>2}. {result.name:<20} {where:<22} finished {ordinal(result.place)} with peak chips of {result.peak}, scoring {result.score}")


def ordinal(number: int) -> str:
    suffix = "th" if 10 <= number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def ending(tournament: Tournament) -> list[str]:
    # The lines shown in a window once the tournament is over
    standings = tournament.standings()
    most = standings[0].stack
    leaders = [result.name for result in standings if result.stack == most]
    lines = [f"{leaders[0]} wins with {most:,} chips" if len(leaders) == 1 else f"{' and '.join(leaders)} tie on {most:,} chips"]

    if len(tournament.tables) > 1:
        lines += [f"{ordinal(result.place)}  {result.name}" for result in standings[1:3]]

    return lines


def load_players(args: argparse.Namespace, rules: Rules) -> tuple[list[tuple[str, AI]], dict[str, Team], Sandbox | None]:
    # The teams from --snapshots, each in a container of its own unless --no-sandbox is given, and any other AIs, which are
    # the organiser's own and run here. Returns the players, which team each is, and the sandbox, to stop when it's over.
    bots, teams = load_snapshots(args.snapshots) if args.snapshots else ([], {})
    sandbox = None

    if bots and not args.no_sandbox:
        sandbox = Sandbox(image=args.image, timeout=rules.timeout, seed=args.seed, logs=Path(args.logs))
        ais = sandbox.start([(name, path.parent, teams[name].repo) for name, path in bots])
    else:
        ais = load_ais([f"{name}={path}" for name, path in bots], least=0)

    ais += load_ais(args.ais, least=0, taken=[name for name, _ in ais])

    if len(ais) < 2:
        if sandbox:
            sandbox.stop()

        raise SystemExit(f"poker: expected at least 2 AIs, but there were {len(ais)}")

    if args.snapshots:
        # Seats are drawn at random, as in a real tournament, and the same seed draws them the same way
        random.Random(args.seed).shuffle(ais)

    return ais, teams, sandbox


def run(args: argparse.Namespace):
    rules = load_rules(args)
    ais, teams, sandbox = load_players(args, rules)

    try:
        watch(args, ais, teams, rules)
    finally:
        if sandbox:
            sandbox.stop()


def watch(args: argparse.Namespace, ais: list[tuple[str, AI]], teams: dict[str, Team], rules: Rules):
    from .render import CONTROLS  # Imported here so that poker test works without a screen
    from .window import Windows

    print(f"Controls: {CONTROLS}")
    tournament = new_tournament(args, ais, rules)
    title = "MATCH OVER" if len(tournament.tables) == 1 else "TOURNAMENT OVER"
    windows = Windows(total_hands=rules.hands, fullscreen=args.fullscreen, sys_path=STARTING_PATH)
    told: dict[int, str] = {}  # What each window has been told about how its table ended

    def tell_windows():
        # Lets each window know once its table has nothing more to play, so it can say why after its last hand
        over = tournament.is_over()

        for table in tournament.tables:
            # A table which is down to one player is still in play, as players may be moved to it, so its window carries on
            if table.closed:
                news = "closed"
            elif over:
                news = "over"
            elif not table.in_play():
                news = "waiting"
            else:
                continue

            if told.get(table.number) == news:
                continue

            told[table.number] = news

            if news == "closed":
                moved = " and ".join(str(number) for number in table.moved_to)
                windows.send(table.number, "finish", "TABLE CLOSED", [f"Everyone here moved to table{'s' if len(table.moved_to) > 1 else ''} {moved}"], False, 4.0)
            elif news == "over":
                windows.send(table.number, "finish", title, ending(tournament), True, None)
            else:
                windows.send(table.number, "finish", "TABLE FINISHED", [f"All {rules.hands} hands have been played here", "Waiting for the other tables"], True, None)

    def seating() -> dict[int, list[str]]:
        return {table.number: [seat.name for seat in table.match.seats] for table in tournament.tables}

    windows.start(seating())
    waiting: list[int] = []  # Tables whose windows are ready for their next hand, in the order they asked

    def deal_to_waiting():
        # The tables play hand for hand, so a table can be ready before it may deal. Every hand played may let another table go.
        dealt = True

        while dealt:
            dealt = False

            for number in list(waiting):
                table = tournament.tables[number - 1]

                if tournament.is_over() or not table.in_play():
                    waiting.remove(number)  # It has nothing more to play, and tell_windows says why. A table which is only waiting for players stays.

                elif tournament.may_deal(table):
                    waiting.remove(number)
                    windows.send(number, "hand", tournament.play_hand(table))
                    tell_windows()
                    dealt = True

    try:
        # Each window asks for its next hand once it has shown the last one, and the hand is played just before it is sent.
        # Moving players between tables happens straight after a hand, while every table is between hands.
        while windows.open:
            event = windows.next_event()

            if event is None:
                continue

            number, message = event

            if message == "need":
                if number not in waiting:
                    waiting.append(number)

                deal_to_waiting()

            elif message == "restart":
                tournament = new_tournament(args, ais, rules)
                told = {}
                waiting = []
                windows.start(seating())

            elif message == "lost":
                windows.open_window(number, seating()[number])

            elif message == "closed" and told.get(number) != "closed":
                break  # Closing the window of a table which is still playing ends everything, as ESC always has

    except KeyboardInterrupt:
        print()  # Ctrl+C stops the windows, and the results so far are still printed

    finally:
        windows.close()

    print_standings(tournament)

    if args.results:
        write_results(args.results, tournament, teams, args.seed)


def test(args: argparse.Namespace):
    rules = load_rules(args)
    ais, _, sandbox = load_players(args, rules)

    try:
        play_matches(args, ais, rules)
    finally:
        if sandbox:
            sandbox.stop()


def play_matches(args: argparse.Namespace, ais: list[tuple[str, AI]], rules: Rules):
    rng = random.Random(args.seed)

    chips = {name: 0 for name, _ in ais}
    wins = {name: 0.0 for name, _ in ais}
    places = {name: 0 for name, _ in ais}
    errors = {name: 0 for name, _ in ais}

    for number in range(args.matches):
        seed = None if args.seed is None else args.seed + number

        if seed is not None:
            random.seed(seed)

        tournament = Tournament(ais=rng.sample(ais, len(ais)), rules=rules, seed=seed)  # Seats are shuffled every match
        tournament.play()

        standings = tournament.standings()
        leaders = [result for result in standings if result.stack == standings[0].stack]

        for result in standings:
            chips[result.name] += result.stack
            places[result.name] += result.place
            errors[result.name] += result.errors

        for result in leaders:
            wins[result.name] += 1 / len(leaders)

    width = max(len(name) for name in chips)
    tables = -(-len(ais) // TABLE_SIZE)
    length = (f"of up to {rules.hands} hands" + (" a table" if tables > 1 else "")) if rules.hands else "played until one AI has every chip"
    print(f"{args.matches} matches {length}" + (f", starting on {tables} tables" if tables > 1 else ""))
    print(f"{'AI':<{width}}  {'Won':>6}  {'Avg chips':>9}  {'Avg place':>9}  {'Bad actions':>11}")

    for name in sorted(chips, key=lambda name: (wins[name], chips[name]), reverse=True):  # Best win rate first, then most chips
        print(f"{name:<{width}}  {wins[name] / args.matches:>6.1%}  {chips[name] / args.matches:>9.1f}  {places[name] / args.matches:>9.2f}  {errors[name]:>11}")


def score(args: argparse.Namespace):
    (_, ai), = load_ais([args.ai], least=1)
    score_ai(ai, args.output)


def main(argv: list[str] | None = None):
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument("--rules", metavar="FILE", help="a yaml file of rules to play by, like poker/internals/rules.yaml. It only needs the rules which are different")
    options.add_argument("--hands", type=whole, help="most hands each table plays, or 0 to play until one AI has every chip, in place of what the rules say")
    options.add_argument("--stack", type=positive, help="chips each AI starts with, in place of what the rules say")
    options.add_argument("--blinds", type=parse_blinds, metavar="SMALL/BIG", help="the blinds at the start, like 10/20, in place of what the rules say")
    options.add_argument("--timeout", type=float, metavar="SECONDS", help="how long an AI gets for each action, or 0 for no limit, in place of what the rules say")

    seeded = argparse.ArgumentParser(add_help=False, parents=[options])
    seeded.add_argument("--seed", type=int, help="makes the cards the same every time")

    ais_help = f"path to a python file with a myAI function, or NAME=PATH to choose the name it is shown with (at least 2, and more than {TABLE_SIZE} are split between tables)"

    parser = argparse.ArgumentParser(prog="poker", description="Play poker AIs against each other.")
    commands = parser.add_subparsers(dest="command", required=True)

    snapshots = argparse.ArgumentParser(add_help=False)
    snapshots.add_argument("--snapshots", metavar="FOLDER", help="also play every team's bot from a folder made by the website's db/download-snapshots.ts, each in a Docker container of its own")
    snapshots.add_argument("--image", default=IMAGE, help=f"the Docker image to run the teams' bots in ({IMAGE}, which the competitions repo's results/run.sh builds, if left out)")
    snapshots.add_argument("--logs", default="bot-logs", metavar="FOLDER", help="where to keep what each team's bot prints (bot-logs if left out)")
    snapshots.add_argument("--no-sandbox", action="store_true", help="run the teams' bots here instead of in containers. Their code can then do anything you can, so only use this for bots you trust")

    run_parser = commands.add_parser("run", parents=[seeded, snapshots], help="play a match and watch it, with a window for each table")
    run_parser.add_argument("ais", nargs="*", metavar="AI", help=ais_help)
    run_parser.add_argument("--results", metavar="FILE", help="write everyone's result to this file, for the website's db/record-tournament.ts")
    run_parser.add_argument("--fullscreen", action="store_true", help="start with the window filling the screen")
    run_parser.set_defaults(function=run)

    test_parser = commands.add_parser("test", parents=[seeded, snapshots], help="play many matches without watching and print the results")
    test_parser.add_argument("matches", type=positive, help="how many matches to play")
    test_parser.add_argument("ais", nargs="*", metavar="AI", help=ais_help)
    test_parser.set_defaults(function=test)

    score_parser = commands.add_parser("score", help="score an AI as the competition does when you push, and write the score to a file")
    score_parser.add_argument("ai", nargs="?", default="myAI.py", metavar="AI", help="path to a python file with a myAI function (myAI.py if left out)")
    score_parser.add_argument("--output", default="score.txt", metavar="FILE", help="where to write the score (score.txt if left out)")
    score_parser.set_defaults(function=score)

    args = parser.parse_args(argv)
    args.function(args)


if __name__ == "__main__":
    main()
