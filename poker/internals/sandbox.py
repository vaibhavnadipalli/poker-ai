from __future__ import annotations

import importlib.util
import json
import os
import random
import select
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from ..action import Action
from ..card import Card, Rank, Suit
from ..game_state import GameState
from ..player import Blind, MyPlayer, Player


# Each team's bot can be run in a container of its own, so that its code never runs on the organiser's computer. The engine
# and the windows stay where they are: when it is a bot's turn, the engine sends its container the game state as a line of
# JSON, and the bot's action comes back the same way. Nothing the bot sends is unpickled or run, it is only read as JSON.
#
# The containers are made from the competitions repo's Docker image, which its results/run.sh builds, with the same limits:
# no network, a read-only file system, no privileges, and little memory and CPU. Each one can only see its own team's
# snapshot and this poker package. A bot also gets its own Python process, so it can't read the deck, change another bot's
# random numbers or tamper with the engine.

IMAGE = "wai-results"
START_TIMEOUT = 120  # Seconds for every container to start and load its bot
LONGEST_MESSAGE = 1 << 16
LONGEST_LOG = 1 << 20  # A bot's log is cut off after this many bytes, so that one which prints forever can't fill the disk
ENGINE = Path(__file__).resolve().parent.parent  # This poker package, which is mounted into each container read-only


class BotProblem(Exception):
    # Raised in place of a sandboxed bot's action when it went wrong, with the reason worded as it would be for a bot run directly
    pass


def readable(text) -> str:
    # A reason sent by a bot's container, made safe to show: it could have been written by the bot itself, so anything which
    # isn't plain text, such as the codes a terminal acts on, is replaced
    if not isinstance(text, str):
        return "went wrong"

    return "".join(character if character.isprintable() else "?" for character in text[:200])


# ---- The messages

RANKS = {rank.value: rank for rank in Rank}
SUITS = {suit.value: suit for suit in Suit}
BLINDS = {blind.value: blind for blind in Blind}
KINDS = {kind.value: kind for kind in Action.Kind}


def state_to_json(state: GameState) -> dict:
    return {
        "players": [
            {
                "me": player is state.my_player,
                "blind": player.blind.value if player.blind else None,
                "has_folded": player.has_folded,
                "chips_in_stack": player.chips_in_stack,
                "chips_bet": player.chips_bet,
            }
            for player in state.players
        ],
        "hole_cards": [[card.rank.value, card.suit.value] for card in state.my_player.hole_cards],
        "chips_in_pot": state.chips_in_pot,
        "community_cards": [[card.rank.value, card.suit.value] for card in state.community_cards],
        "small_blind": state.small_blind,
        "big_blind": state.big_blind,
        "min_raise": state.min_raise,
        "ante": state.ante,
    }


def state_from_json(data: dict) -> GameState:
    def card(pair: list) -> Card:
        rank, suit = pair
        return Card(RANKS[rank], SUITS[suit])

    my_player = None
    players = []

    for entry in data["players"]:
        blind = BLINDS[entry["blind"]] if entry["blind"] is not None else None

        if entry["me"]:
            my_player = MyPlayer(blind=blind, chips_in_stack=entry["chips_in_stack"], chips_bet=entry["chips_bet"], hole_cards={card(pair) for pair in data["hole_cards"]})
            players.append(my_player)
        else:
            players.append(Player(blind=blind, has_folded=entry["has_folded"], chips_in_stack=entry["chips_in_stack"], chips_bet=entry["chips_bet"]))

    return GameState(my_player=my_player, players=players, chips_in_pot=data["chips_in_pot"], community_cards={card(pair) for pair in data["community_cards"]}, small_blind=data["small_blind"], big_blind=data["big_blind"], min_raise=data["min_raise"], ante=data["ante"])


def action_to_json(action: Action) -> dict:
    return {"kind": action.kind.value, "amount": action.amount}


def action_from_json(data) -> Action:
    # Only an action exactly like one a bot could have made is accepted
    if not isinstance(data, dict) or not isinstance(data.get("kind"), str) or data["kind"] not in KINDS:
        raise BotProblem("sent something which isn't an action")

    amount = data.get("amount")

    if amount is not None and (not isinstance(amount, int) or isinstance(amount, bool)):
        raise BotProblem("sent something which isn't an action")

    try:
        return Action(KINDS[data["kind"]], amount)
    except (TypeError, ValueError) as e:
        raise BotProblem(f"sent an action which isn't allowed: {e}"[:200])


# ---- The organiser's side

class SandboxedBot:
    # Stands in for a bot, as the engine expects: called with the game state, it returns the bot's action
    def __init__(self, name: str, command: list[str], log: Path, timeout: float):
        self.name = name
        self.timeout = timeout
        self.log = log
        self.buffer = b""
        self.requests = 0
        self.failure: str | None = None  # Why it can't play any more, once that is known

        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self.logger = threading.Thread(target=copy_log, args=(self.process.stderr, log), daemon=True)
        self.logger.start()

    def __call__(self, state: GameState) -> Action:
        if self.failure:
            raise BotProblem(self.failure)

        self.requests += 1
        request = self.requests

        try:
            self.process.stdin.write(json.dumps({"id": request, "state": state_to_json(state)}).encode() + b"\n")
        except (BrokenPipeError, OSError):
            self.failed("its container stopped")

        # The engine's own time limit normally stops the wait first. This is in case it can't, such as on Windows.
        deadline = time.monotonic() + self.timeout + 1 if self.timeout else None

        while True:
            message = self.read(deadline)

            if message is None or deadline is not None and time.monotonic() > deadline:
                raise BotProblem(f"took longer than {self.timeout:g}s")

            if message.get("id") != request:
                continue  # The answer to an earlier turn, which came too late, or something the bot wrote itself

            if "problem" in message:
                raise BotProblem(readable(message["problem"]))

            return action_from_json(message.get("action"))

    def read(self, deadline: float | None) -> dict | None:
        # The next message from the container, or None if the deadline passes first
        while b"\n" not in self.buffer:
            if len(self.buffer) > LONGEST_MESSAGE:
                self.failed("sent a message which was far too long")

            wait = None if deadline is None else deadline - time.monotonic()

            if wait is not None and wait <= 0:
                return None

            ready, _, _ = select.select([self.process.stdout], [], [], wait)

            if not ready:
                return None

            chunk = os.read(self.process.stdout.fileno(), LONGEST_MESSAGE)

            if not chunk:
                self.failed(f"its container stopped (see {self.log})")

            self.buffer += chunk

        line, _, self.buffer = self.buffer.partition(b"\n")

        try:
            message = json.loads(line)
        except (ValueError, RecursionError):
            return {}  # Something the bot wrote itself, which is ignored

        return message if isinstance(message, dict) else {}

    def failed(self, reason: str):
        self.failure = reason
        raise BotProblem(reason)

    def wait_until_ready(self, deadline: float):
        # The container says it is ready once it has loaded the bot, or why it couldn't
        try:
            while True:
                message = self.read(deadline)

                if message is None:
                    self.failure = f"its container didn't start in time (see {self.log})"
                    return

                if message.get("id") == 0:
                    if "problem" in message:
                        self.failure = readable(message["problem"])
                    return

        except BotProblem:
            pass  # self.failure says why

    def stop(self):
        try:
            self.process.stdin.close()  # The bot's container stops by itself once there are no more turns
        except OSError:
            pass


def copy_log(source, path: Path):
    # Writes what a bot's container prints to its log, up to LONGEST_LOG bytes, then throws the rest away
    written = 0

    with path.open("wb") as file:
        while chunk := source.read(1 << 16):
            if written < LONGEST_LOG:
                file.write(chunk[:LONGEST_LOG - written])
                written += len(chunk)

                if written >= LONGEST_LOG:
                    file.write(b"\n[poker: the rest of this log was cut off]\n")

                file.flush()


class Sandbox:
    # Starts a container for every team's bot, and stops them all again
    def __init__(self, *, image: str, timeout: float, seed: int | None, logs: Path):
        self.image = image
        self.timeout = timeout
        self.seed = seed
        self.logs = logs
        self.bots: list[SandboxedBot] = []
        self.names: list[str] = []  # The containers' names, to stop any which don't stop by themselves
        self.docker = os.environ.get("POKER_DOCKER", "docker")  # Only changed for testing

    def start(self, teams: list[tuple[str, Path, str]]) -> list[tuple[str, SandboxedBot]]:
        # Each team is its name, its snapshot's folder, and its repo, which gives it its own random seed
        if not shutil.which(self.docker):
            raise SystemExit("poker: the teams' bots run in Docker containers, but Docker isn't installed. Install Docker Desktop, start it, and try again")

        self.logs.mkdir(parents=True, exist_ok=True)
        print(f"Starting {len(teams)} bots, each in a container of its own...", file=sys.stderr)

        for name, folder, repo in teams:
            container = f"poker-bot-{uuid.uuid4().hex[:12]}"
            self.names.append(container)
            log = self.logs / (name.replace("/", "__") + ".log")
            self.bots.append(SandboxedBot(name, self.command(container, folder, repo), log, self.timeout))

        deadline = time.monotonic() + START_TIMEOUT

        for bot in self.bots:
            bot.wait_until_ready(deadline)

        broken = [bot for bot in self.bots if bot.failure]

        if broken and len(broken) == len(self.bots):
            self.stop()
            raise SystemExit(f"poker: none of the bots' containers started. Is Docker running, and has the competitions repo's results/run.sh built the {self.image} image? See {self.logs} for each one's output")

        for bot in broken:
            print(f"poker: {bot.name} will check or fold every time, as its bot {bot.failure}", file=sys.stderr)

        print(f"{len(self.bots) - len(broken)} of {len(self.bots)} bots are ready", file=sys.stderr)
        return [(bot.name, bot) for bot in self.bots]

    def command(self, container: str, folder: Path, repo: str) -> list[str]:
        seed = "" if self.seed is None else f"{self.seed}/{repo}"  # Every bot gets its own random numbers, the same each time for a seed

        return [
            self.docker, "run", "--rm", "--interactive", "--pull", "never", "--name", container,
            "--network", "none", "--memory", "512m", "--memory-swap", "512m", "--cpus", "1", "--pids-limit", "64",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:size=64m,mode=1777",
            "--env", "HOME=/tmp", "--env", "PYTHONPATH=/official", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONHASHSEED=0",
            "--volume", f"{Path(folder).resolve()}:/submission:ro",
            "--volume", f"{ENGINE}:/official/poker:ro",
            "--entrypoint", "python", self.image,
            "-m", "poker.internals.sandbox", "/submission/myAI.py", str(self.timeout), seed,
        ]

    def stop(self):
        for bot in self.bots:
            bot.stop()

        deadline = time.monotonic() + 5

        for bot in self.bots:
            try:
                bot.process.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                pass

        running = [name for bot, name in zip(self.bots, self.names) if bot.process.poll() is None]

        if running and self.docker == "docker":
            subprocess.run([self.docker, "kill", *running], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        for bot in self.bots:
            if bot.process.poll() is None:
                bot.process.kill()

        for bot in self.bots:
            bot.logger.join(timeout=1)  # So that the logs are complete


# ---- The container's side

def serve(path: str, timeout: float, seed: str):
    # Runs inside a bot's container: loads its myAI function, then answers each turn the engine sends
    from .engine import TimeLimitExceeded, time_limit

    replies = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)  # Anything the bot prints goes to its log, not to the engine

    def reply(message: dict):
        replies.write(json.dumps(message) + "\n")

    if seed:
        random.seed(seed)

    try:
        folder = str(Path(path).parent)

        if folder not in sys.path:
            sys.path.append(folder)  # So that it can import files next to it. This poker package comes first.

        spec = importlib.util.spec_from_file_location("myAI", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        ai = module.myAI

        if not callable(ai):
            raise TypeError("myAI isn't a function")

    except BaseException as e:
        reply({"id": 0, "problem": f"couldn't be loaded: {type(e).__name__}: {e}"[:200]})
        return

    reply({"id": 0, "ready": True})

    for line in sys.stdin:
        try:
            message = json.loads(line)
            request = message["id"]
            state = state_from_json(message["state"])
        except (ValueError, KeyError, TypeError):
            continue

        try:
            with time_limit(timeout):  # So that a bot which takes too long is ready for its next turn
                result = ai(state)

        except TimeLimitExceeded:
            reply({"id": request, "problem": f"took longer than {timeout:g}s"})
            continue

        except (Exception, SystemExit) as e:  # A bot which tries to exit just loses its turn
            reply({"id": request, "problem": f"raised {type(e).__name__}: {e}"[:200]})
            continue

        if isinstance(result, Action):
            reply({"id": request, "action": action_to_json(result)})
        else:
            reply({"id": request, "problem": f"returned {result!r:.150} instead of an Action"})


if __name__ == "__main__":
    serve(sys.argv[1], float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
