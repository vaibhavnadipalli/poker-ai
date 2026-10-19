from __future__ import annotations

import multiprocessing
import queue
import sys


# raylib can only open one window in a process, so every table is shown by a process of its own. The AIs and the
# tournament stay in the main process, which sends each window the hands played at its table as they are needed.
#
# A window sends the main process (generation, table, message), where the message is one of
#   "need"     it has shown everything it was sent, and is ready for the next hand
#   "restart"  R was pressed
#   "closed"   the window has closed, because ESC was pressed, it was closed, or it closed itself after its table was broken up
# The generation goes up every time the tournament restarts, so that messages sent before a restart can be told apart.
#
# The main process can also be told
#   "lost"     a window closed itself just as the tournament restarted, so it needs opening again
#
# The main process sends a window one of
#   ("hand", hand)                              a hand to show
#   ("finish", title, lines, hints, close_after) there are no more hands to come, so show this once the last one is over
#   ("reset", generation, players)              the tournament has started again
#   ("quit",)                                   close the window


def show_table(number: int, count: int, players: list[str], total_hands: int, fullscreen: bool, generation: int, commands: multiprocessing.Queue, events: multiprocessing.Queue):
    try:
        run_window(number, count, players, total_hands, fullscreen, generation, commands, events)
    except KeyboardInterrupt:
        pass  # Ctrl+C in the terminal reaches every window as well as the main process, which deals with it


def run_window(number: int, count: int, players: list[str], total_hands: int, fullscreen: bool, generation: int, commands: multiprocessing.Queue, events: multiprocessing.Queue):
    from .render import PokerRenderer

    renderer = PokerRenderer(players=players, total_hands=total_hands, fullscreen=fullscreen, title="WAI Poker" if count == 1 else f"WAI Poker - Table {number}", tile=(number - 1, count))
    asked = False

    try:
        while renderer.is_window_open():
            try:
                while True:
                    command = commands.get_nowait()

                    if command[0] == "hand":
                        renderer.push(command[1])
                        asked = False

                    elif command[0] == "finish":
                        renderer.finish(*command[1:])

                    elif command[0] == "reset":
                        generation = command[1]
                        renderer.reset(players=command[2])
                        asked = False

                    elif command[0] == "quit":
                        return

            except queue.Empty:
                pass

            if renderer.should_restart():
                events.put((generation, number, "restart"))

            if not asked and renderer.needs_hand():
                events.put((generation, number, "need"))
                asked = True

            renderer.update()

            if renderer.should_close():
                return

    finally:
        renderer.close()
        events.put((generation, number, "closed"))


class Windows:
    # The windows of every table, from the main process's side
    def __init__(self, *, total_hands: int, fullscreen: bool, sys_path: list[str] | None = None):
        # A window process is started with sys_path as its module search path. The bots' folders are added to it as they are
        # loaded, and a team's snapshot holds its own copy of the poker folder, which a window must never import in place of this one.
        self.sys_path = list(sys_path) if sys_path is not None else list(sys.path)
        self.context = multiprocessing.get_context("spawn")  # The same on every system, and nothing from the main process is copied into a window
        self.events = self.context.Queue()
        self.total_hands = total_hands
        self.fullscreen = fullscreen
        self.processes: dict[int, multiprocessing.Process] = {}
        self.commands: dict[int, multiprocessing.Queue] = {}
        self.open: set[int] = set()
        self.reset_sent: set[int] = set()  # The windows told to start again at the latest restart
        self.count = 0
        self.generation = 0

    def start(self, tables: dict[int, list[str]]):
        # Opens a window for every table, or starts again in the windows which are still open
        self.generation += 1
        self.count = len(tables)
        self.reset_sent = set()

        for number, players in tables.items():
            if number in self.open and self.processes[number].is_alive():
                self.send(number, "reset", self.generation, players)
                self.reset_sent.add(number)
            else:
                self.open_window(number, players)

    def open_window(self, number: int, players: list[str]):
        if number in self.processes:
            self.processes[number].join(timeout=1)
            self.forget_queue(self.commands[number])

        self.commands[number] = self.context.Queue()
        process = self.context.Process(target=show_table, args=(number, self.count, players, self.total_hands, self.fullscreen, self.generation, self.commands[number], self.events), daemon=True)
        searched = sys.path[:]
        sys.path[:] = self.sys_path  # A spawned process is given the search path in place when it starts

        try:
            process.start()
        finally:
            sys.path[:] = searched
        self.processes[number] = process
        self.open.add(number)

    @staticmethod
    def forget_queue(commands: multiprocessing.Queue):
        # Anything still waiting in the queue of a window which has gone is thrown away, rather than holding up the exit
        commands.cancel_join_thread()
        commands.close()

    def send(self, number: int, *command):
        if number in self.open:
            self.commands[number].put(command)

    def next_event(self) -> tuple[int, str] | None:
        # Waits for a window to say something. Anything sent before the latest restart is dropped, apart from a window closing.
        while True:
            try:
                generation, number, message = self.events.get(timeout=0.5)
                break

            except queue.Empty:
                # A window which crashed before it could say so, such as when raylib can't open it, counts as closed
                for number in sorted(self.open):
                    if not self.processes[number].is_alive():
                        self.open.discard(number)
                        return number, "closed"

        if message == "closed":
            if number not in self.open:
                return None

            self.open.discard(number)

            if generation == self.generation:
                return number, message

            # It closed itself before it heard about the restart, so the table it should now be showing has no window
            return (number, "lost") if number in self.reset_sent else None

        if generation != self.generation or number not in self.open:
            return None

        return number, message

    def close(self):
        for number in list(self.open):
            self.send(number, "quit")

        for process in self.processes.values():
            process.join(timeout=2)

            if process.is_alive():
                process.terminate()

        for commands in self.commands.values():
            self.forget_queue(commands)
