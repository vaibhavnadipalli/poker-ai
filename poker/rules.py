from __future__ import annotations

from pathlib import Path

import yaml


DEFAULT_RULES = Path(__file__).parent / "rules.yaml"


class Rules:
    # The rules of a match. They come from rules.yaml, and anything in the given file replaces what is there.
    def __init__(self, path: str | Path | None = None):
        rules = yaml.safe_load(DEFAULT_RULES.read_text(encoding="utf-8"))

        if path is not None:
            self.replace(rules, yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}, str(path))

        self.hands: int = rules["hands"]
        self.stack: int = rules["stack"]
        self.timeout: float = rules["timeout"]

        self.small_blind: int = rules["blinds"]["small"]
        self.big_blind: int = rules["blinds"]["big"]

        self.blinds_up_every_orbits: int = rules["blinds_go_up"]["every_orbits"]
        self.blinds_up_every_hands: int = rules["blinds_go_up"]["every_hands"]
        self.blind_levels: list[float] = rules["blinds_go_up"]["levels"]

        self.cut_every_orbits: int = rules["chips_cut"]["every_orbits"]
        self.cut_every_hands: int = rules["chips_cut"]["every_hands"]
        self.cut_share: float = rules["chips_cut"]["share"]

        self.ante: int = rules["ante"]["chips"]
        self.ante_from_orbit: int = rules["ante"]["from_orbit"]

        self.check()

    @staticmethod
    def replace(rules: dict, changes: dict, where: str):
        if not isinstance(changes, dict):
            raise ValueError(f"Expected {where} to hold rules like {', '.join(rules)}, but it holds {changes!r}")

        for name, value in changes.items():
            if name not in rules:
                raise ValueError(f"There is no rule called {name} in {where}. The rules there are {', '.join(rules)}")

            if isinstance(rules[name], dict):
                Rules.replace(rules[name], value, f"{name} in {where}")
            else:
                rules[name] = value

    def check(self):
        # Changes made after the rules are loaded, such as from the command line, can be checked by calling this again
        def whole(name: str, value, least: int):
            if not isinstance(value, int) or isinstance(value, bool) or value < least:
                raise ValueError(f"Expected {name} to be a whole number of at least {least}, but it was {value!r}")

        def number(name: str, value, least: float, below: float | None = None):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < least or (below is not None and value >= below):
                raise ValueError(f"Expected {name} to be a number of at least {least}" + (f" and less than {below}" if below is not None else "") + f", but it was {value!r}")

        whole("hands", self.hands, 1)
        whole("stack", self.stack, 1)
        number("timeout", self.timeout, 0)

        whole("the small blind", self.small_blind, 1)
        whole("the big blind", self.big_blind, self.small_blind)

        for name, orbits, hands in (("blinds_go_up", self.blinds_up_every_orbits, self.blinds_up_every_hands), ("chips_cut", self.cut_every_orbits, self.cut_every_hands)):
            whole(f"every_orbits in {name}", orbits, 0)
            whole(f"every_hands in {name}", hands, 0)

            if orbits and hands:
                raise ValueError(f"Expected only one of every_orbits and every_hands in {name} to be more than 0, but they were {orbits} and {hands}")

        if not isinstance(self.blind_levels, list) or not self.blind_levels:
            raise ValueError(f"Expected levels in blinds_go_up to be a list of numbers, but it was {self.blind_levels!r}")

        for index, level in enumerate(self.blind_levels):
            number("each of the levels in blinds_go_up", level, 0)

            if level <= (self.blind_levels[index - 1] if index else 0) or level >= 10 * self.blind_levels[0]:
                raise ValueError(f"Expected the levels in blinds_go_up to get bigger, and to stay under ten times the first, but they were {self.blind_levels}")

        number("share in chips_cut", self.cut_share, 0, 1)
        whole("chips in ante", self.ante, 0)
        whole("from_orbit in ante", self.ante_from_orbit, 1)
