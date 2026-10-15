from __future__ import annotations

import argparse
import importlib.util
import random
import sys
from pathlib import Path

import yaml

from .engine import AI, Match
from .rules import Rules


MAX_PLAYERS = 8


def load_ais(specs: list[str]) -> list[tuple[str, AI]]:
    # Each spec is a path to a python file with a myAI function, optionally written as NAME=PATH
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

        taken = [other for other, _ in ais]
        base = name
        number = 2

        while name in taken:
            name = f"{base} {number}"
            number += 1

        ais.append((name, module.myAI))

    if not 2 <= len(ais) <= MAX_PLAYERS:
        raise SystemExit(f"poker: expected between 2 and {MAX_PLAYERS} AIs, but there were {len(ais)}")

    return ais


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


def load_rules(args: argparse.Namespace) -> Rules:
    # The rules come from poker/rules.yaml or the file given with --rules, and then the command line can change a few of them
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


def new_match(args: argparse.Namespace, ais: list[tuple[str, AI]], rules: Rules) -> Match:
    if args.seed is not None:
        random.seed(args.seed)  # For AIs which use the random module

    return Match(ais=ais, rules=rules, seed=args.seed)


def print_standings(match: Match):
    print(f"Played {len(match.hands)} hands")

    for place, seat in enumerate(match.standings(), start=1):
        notes = [f"out on hand {seat.busted_on}"] if seat.busted_on else []
        notes += [f"{seat.errors} bad actions"] if seat.errors else []
        print(f"{place}. {seat.name:<20} {seat.stack:>8}" + (f"  ({', '.join(notes)})" if notes else ""))


def run(args: argparse.Namespace):
    ais = load_ais(args.ais)
    rules = load_rules(args)

    from .render import CONTROLS, PokerRenderer  # Imported here so that poker test works without a screen

    print(f"Controls: {CONTROLS}")
    match = new_match(args, ais, rules)
    renderer = PokerRenderer(players=[name for name, _ in ais], total_hands=rules.hands, fullscreen=args.fullscreen)

    # The main loop runs whilst the window is open, playing each hand just before it is shown
    while renderer.is_window_open():
        if renderer.should_restart():
            match = new_match(args, ais, rules)
            renderer.reset()

        if renderer.needs_hand():
            match.play_hand(len(match.hands) + 1)
            renderer.push(match.hands[-1])

            if len(match.hands) >= rules.hands or match.is_over():
                renderer.finish()

        renderer.update()

    renderer.close()
    print_standings(match)


def test(args: argparse.Namespace):
    ais = load_ais(args.ais)
    rules = load_rules(args)
    rng = random.Random(args.seed)

    chips = {name: 0 for name, _ in ais}
    wins = {name: 0.0 for name, _ in ais}
    places = {name: 0 for name, _ in ais}
    errors = {name: 0 for name, _ in ais}

    for number in range(args.matches):
        seed = None if args.seed is None else args.seed + number

        if seed is not None:
            random.seed(seed)

        match = Match(ais=rng.sample(ais, len(ais)), rules=rules, seed=seed)  # Seats are shuffled every match
        match.play()

        standings = match.standings()
        leaders = [seat for seat in standings if seat.stack == standings[0].stack]

        for place, seat in enumerate(standings, start=1):
            chips[seat.name] += seat.stack
            places[seat.name] += place
            errors[seat.name] += seat.errors

        for seat in leaders:
            wins[seat.name] += 1 / len(leaders)

    width = max(len(name) for name in chips)
    print(f"{args.matches} matches of up to {rules.hands} hands")
    print(f"{'AI':<{width}}  {'Won':>6}  {'Avg chips':>9}  {'Avg place':>9}  {'Bad actions':>11}")

    for name in sorted(chips, key=lambda name: (wins[name], chips[name]), reverse=True):  # Best win rate first, then most chips
        print(f"{name:<{width}}  {wins[name] / args.matches:>6.1%}  {chips[name] / args.matches:>9.1f}  {places[name] / args.matches:>9.2f}  {errors[name]:>11}")


def main(argv: list[str] | None = None):
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument("--rules", metavar="FILE", help="a yaml file of rules to play by, like poker/rules.yaml. It only needs the rules which are different")
    options.add_argument("--hands", type=positive, help="most hands to play in a match, in place of what the rules say")
    options.add_argument("--stack", type=positive, help="chips each AI starts with, in place of what the rules say")
    options.add_argument("--blinds", type=parse_blinds, metavar="SMALL/BIG", help="the blinds at the start, like 10/20, in place of what the rules say")
    options.add_argument("--timeout", type=float, metavar="SECONDS", help="how long an AI gets for each action, or 0 for no limit, in place of what the rules say")
    options.add_argument("--seed", type=int, help="makes the cards the same every time")

    ais_help = f"path to a python file with a myAI function, or NAME=PATH to choose the name it is shown with (2 to {MAX_PLAYERS} of them)"

    parser = argparse.ArgumentParser(prog="poker", description="Play poker AIs against each other.")
    commands = parser.add_subparsers(dest="command", required=True)

    run_parser = commands.add_parser("run", parents=[options], help="play a match and watch it")
    run_parser.add_argument("ais", nargs="+", metavar="AI", help=ais_help)
    run_parser.add_argument("--fullscreen", action="store_true", help="start with the window filling the screen")
    run_parser.set_defaults(function=run)

    test_parser = commands.add_parser("test", parents=[options], help="play many matches without watching and print the results")
    test_parser.add_argument("matches", type=positive, help="how many matches to play")
    test_parser.add_argument("ais", nargs="+", metavar="AI", help=ais_help)
    test_parser.set_defaults(function=test)

    args = parser.parse_args(argv)
    args.function(args)


if __name__ == "__main__":
    main()
