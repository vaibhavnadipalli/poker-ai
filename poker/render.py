from __future__ import annotations

import math
from pathlib import Path

import pyray as rl


WIDTH, HEIGHT = 1280, 720  # Everything is laid out for a window of this size, and scaled to fit whatever size the window really is
CANVAS_ZOOM = 2  # The picture is drawn at this many times that size before it is scaled, so that it stays sharp in a bigger window
TABLE_WIDTH = 1000  # The table is on the left, with a panel down the right

# The cards and chips are drawn at one and a half times the size of their pixels. Their pictures are enlarged to three
# times the size when they are loaded and then drawn at half of that, which keeps every pixel the same width.
ZOOM = 1.5
TEXTURE_ZOOM = 3

CARD_WIDTH, CARD_HEIGHT = int(48 * ZOOM), int(64 * ZOOM)
RANKS = "A23456789TJQK"  # The order of the columns in cards.png
SUIT_ROWS = {"h": 0, "d": 1, "s": 2, "c": 3}

# What each colour of chip is worth, and the row and half of chips.png it is in. Each has four pictures, of taller and taller stacks.
CHIPS = [(5000, 2, 1), (1000, 3, 1), (500, 1, 1), (100, 3, 0), (25, 2, 0), (10, 0, 1), (5, 0, 0), (1, 1, 0)]
CHIP_WIDTH, CHIP_HEIGHT = int(32 * ZOOM), int(48 * ZOOM)
CHIP_SPACING = 30

CENTRE = (500, 316)
SEATS = (405, 233)  # How far the players sit from the centre of the table, across and down
BETS_CENTRE = (500, 323)
BETS = (260, 127)
BETS_SHAPE = (1.6, 0.15)  # Bends the ring of bets into more of a rectangle, which keeps them clear of the players and the board
BOARD_Y = 220
POT = (500, 376)

SPEEDS = [0.5, 1, 2, 4, 8, 16]
ANIMATION = 0.35  # Seconds spent moving cards and chips at the start of each thing that happens
HOLDS = {"deal": 0.7, "ante": 0.4, "blind": 0.3, "fold": 0.5, "check": 0.5, "call": 0.6, "raise": 0.8, "return": 0.6, "street": 0.9, "showdown": 1.2, "win": 1.8, "bust": 1.0}

CONTROLS = "SPACE pause    LEFT / RIGHT step    UP / DOWN speed    N next hand    F fullscreen    R restart    ESC quit"


def lerp(start: float, end: float, amount: float) -> float:
    return start + (end - start) * amount


def ease(amount: float) -> float:
    amount = max(0.0, min(1.0, amount))
    return 1 - (1 - amount) ** 3


class PokerRenderer:
    def __init__(self, *, players: list[str], total_hands: int, fullscreen: bool = False, render_fps: int = 60):
        self.players = [name.encode("ascii", "replace").decode() for name in players]  # The font only has ASCII
        self.total_hands = total_hands

        # Everything played so far, and where playback has got to in it
        self.hands: list[dict] = []
        self.hand = 0
        self.frame = 0
        self.clock = 0.0
        self.speed = 1
        self.paused = False
        self.finished = False
        self.step_requested = False
        self.restart_requested = False
        self.prepared_hand = -1
        self.log_lines: list[tuple[int, str, str]] = []
        self.pot_chips: list[dict[int, int]] = []

        self.BACKGROUND = rl.Color(18, 18, 18, 255)
        self.PANEL = rl.Color(28, 28, 27, 255)
        self.PLATE = rl.Color(40, 40, 38, 255)
        self.LINE = rl.Color(70, 70, 66, 255)
        self.FELT = rl.Color(31, 115, 80, 255)
        self.RAIL = rl.Color(59, 42, 32, 255)
        self.TEXT = rl.Color(255, 255, 255, 255)
        self.SOFT = rl.Color(195, 194, 183, 255)
        self.MUTED = rl.Color(137, 135, 129, 255)
        self.GOLD = rl.Color(244, 196, 48, 255)
        self.WARNING = rl.Color(250, 178, 25, 255)
        self.PLAYER_COLOURS = [rl.Color(*colour, 255) for colour in ((57, 135, 229), (217, 89, 38), (25, 158, 112), (201, 133, 0), (213, 81, 129), (0, 131, 0), (144, 133, 233), (230, 103, 103))]

        rl.set_trace_log_level(rl.LOG_NONE)
        rl.set_config_flags(rl.FLAG_WINDOW_RESIZABLE)
        rl.init_window(WIDTH, HEIGHT, "WAI Poker")
        rl.set_window_min_size(WIDTH // 2, HEIGHT // 2)

        if fullscreen:
            rl.toggle_borderless_windowed()

        self.canvas = rl.load_render_texture(WIDTH * CANVAS_ZOOM, HEIGHT * CANVAS_ZOOM)
        rl.set_texture_filter(self.canvas.texture, rl.TEXTURE_FILTER_BILINEAR)
        rl.set_target_fps(render_fps)
        self.window_initialized = True

        self.cards = self.load_sprites("cards.png")
        self.chips = self.load_sprites("chips.png")

    def load_sprites(self, name: str) -> rl.Texture:
        image = rl.load_image(str(Path(__file__).parent / "assets" / name))
        rl.image_resize_nn(image, image.width * TEXTURE_ZOOM, image.height * TEXTURE_ZOOM)
        texture = rl.load_texture_from_image(image)
        rl.unload_image(image)
        rl.set_texture_filter(texture, rl.TEXTURE_FILTER_BILINEAR)
        return texture

    # ---- What the game loop calls

    def is_window_open(self) -> bool:
        return self.window_initialized and not rl.window_should_close()

    def needs_hand(self) -> bool:
        # True once everything pushed so far has been shown
        if self.finished:
            return False

        if not self.hands:
            return True

        return self.at_end() and (self.step_requested or (not self.paused and self.clock >= self.duration()))

    def push(self, hand: dict):
        self.hands.append(hand)

        if self.step_requested:
            self.step_requested = False
            self.advance()

    def finish(self):
        # There are no more hands to come
        self.finished = True

    def should_restart(self) -> bool:
        if self.restart_requested:
            self.restart_requested = False
            return True

        return False

    def reset(self):
        self.hands = []
        self.hand = 0
        self.frame = 0
        self.clock = 0.0
        self.finished = False
        self.step_requested = False
        self.prepared_hand = -1

    def update(self):
        if not self.is_window_open():
            return

        self.handle_keys()

        if self.hands:
            self.clock += rl.get_frame_time() * SPEEDS[self.speed]

            if self.clock >= self.duration():
                if self.paused or not self.advance():
                    self.clock = self.duration()

        self.draw()

    def close(self):
        if self.window_initialized:
            rl.unload_texture(self.cards)
            rl.unload_texture(self.chips)
            rl.unload_render_texture(self.canvas)
            rl.close_window()
            self.window_initialized = False

    # ---- Playback

    def frames(self) -> list[dict]:
        return self.hands[self.hand]["frames"]

    def duration(self) -> float:
        return ANIMATION + HOLDS[self.frames()[self.frame]["kind"]]

    def at_end(self) -> bool:
        return self.hand == len(self.hands) - 1 and self.frame == len(self.frames()) - 1

    def advance(self) -> bool:
        if self.frame < len(self.frames()) - 1:
            self.frame += 1
        elif self.hand < len(self.hands) - 1:
            self.hand += 1
            self.frame = 0
        else:
            return False

        self.clock = 0.0
        return True

    def step_back(self):
        if self.frame > 0:
            self.frame -= 1
        elif self.hand > 0:
            self.hand -= 1
            self.frame = len(self.frames()) - 1

        self.clock = self.duration()

    def handle_keys(self):
        pressed = lambda key: rl.is_key_pressed(key) or rl.is_key_pressed_repeat(key)

        if rl.is_key_pressed(rl.KEY_F) or rl.is_key_pressed(rl.KEY_F11):
            rl.toggle_borderless_windowed()

        if rl.is_key_pressed(rl.KEY_R):
            self.restart_requested = True

        if rl.is_key_pressed(rl.KEY_SPACE):
            self.paused = not self.paused

        if pressed(rl.KEY_UP):
            self.speed = min(self.speed + 1, len(SPEEDS) - 1)

        if pressed(rl.KEY_DOWN):
            self.speed = max(self.speed - 1, 0)

        if not self.hands:
            return

        if pressed(rl.KEY_RIGHT):
            self.paused = True
            self.step_requested = not self.advance() and not self.finished

        if pressed(rl.KEY_LEFT):
            self.paused = True
            self.step_requested = False
            self.step_back()

        if rl.is_key_pressed(rl.KEY_N):
            if self.hand < len(self.hands) - 1:
                self.hand += 1
                self.frame = 0
                self.clock = 0.0
            else:
                self.frame = len(self.frames()) - 1
                self.clock = self.duration()
                self.step_requested = self.paused and not self.finished

    # ---- Drawing

    def draw(self):
        # The picture is drawn onto a canvas of a fixed size, which is then stretched over the window
        rl.begin_texture_mode(self.canvas)
        rl.begin_mode_2d(rl.Camera2D(rl.Vector2(0, 0), rl.Vector2(0, 0), 0, CANVAS_ZOOM))
        rl.clear_background(self.BACKGROUND)
        self.draw_table()

        if self.hands:
            hand = self.hands[self.hand]
            now = hand["frames"][self.frame]

            if self.prepared_hand != self.hand:
                self.prepare(hand)

            before = hand["frames"][self.frame - 1] if self.frame > 0 else {**now, "board": 0, "pot": 0, "bets": [0] * len(self.players)}
            moved = min(1.0, self.clock / ANIMATION)

            self.draw_board(hand, before, now, moved)
            self.draw_seats(hand, before, now, moved)
            self.draw_chips(before, now, ease(moved))
            self.draw_text_centred(self.fit(now["text"], 20, TABLE_WIDTH - 60), TABLE_WIDTH // 2, 636, 20, self.TEXT)
            self.draw_panel(hand, now)

            if self.finished and self.at_end() and self.clock >= self.duration():
                self.draw_match_over(now)
        else:
            self.draw_panel(None, None)

        self.draw_footer()
        rl.end_mode_2d()
        rl.end_texture_mode()

        scale = min(rl.get_screen_width() / WIDTH, rl.get_screen_height() / HEIGHT)
        target = rl.Rectangle((rl.get_screen_width() - WIDTH * scale) / 2, (rl.get_screen_height() - HEIGHT * scale) / 2, WIDTH * scale, HEIGHT * scale)
        source = rl.Rectangle(0, 0, WIDTH * CANVAS_ZOOM, -HEIGHT * CANVAS_ZOOM)  # Canvases are stored upside down

        rl.begin_drawing()
        rl.clear_background(self.BACKGROUND)
        rl.draw_rectangle(int(target.x + TABLE_WIDTH * scale), 0, rl.get_screen_width(), rl.get_screen_height(), self.PANEL)  # Carries the panel on to the edges of the window
        rl.draw_texture_pro(self.canvas.texture, source, target, rl.Vector2(0, 0), 0, rl.WHITE)
        rl.end_drawing()

    def draw_table(self):
        rl.draw_rectangle_rounded(rl.Rectangle(100, 110, 800, 420), 1.0, 48, self.RAIL)
        rl.draw_rectangle_rounded(rl.Rectangle(110, 120, 780, 400), 1.0, 48, self.FELT)
        rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(128, 138, 744, 364), 1.0, 48, 2, rl.fade(self.TEXT, 0.07))

    def draw_board(self, hand: dict, before: dict, now: dict, moved: float):
        left = CENTRE[0] - (5 * CARD_WIDTH + 4 * 6) // 2
        board = hand["board"]

        for index in range(5):
            x = left + index * (CARD_WIDTH + 6)

            if index >= now["board"]:
                rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, BOARD_Y, CARD_WIDTH, CARD_HEIGHT), 0.1, 6, 2, rl.fade(self.TEXT, 0.14))
                continue

            # Cards which have just been dealt drop in one after another
            arrived = ease(moved * 2 - 0.5 * (index - before["board"])) if index >= before["board"] else 1.0

            if arrived > 0:
                self.draw_card(board[index], x, BOARD_Y - 30 * (1 - arrived), 255, arrived)

    def draw_seats(self, hand: dict, before: dict, now: dict, moved: float):
        amount = ease(moved)
        showdown = next((index for index, other in enumerate(hand["frames"]) if other["kind"] == "showdown"), None)
        winners = {seat for other in hand["frames"][:self.frame + 1] for seat in other["winners"]}
        dealing = [seat for seat in range(len(self.players)) if hand["hole_cards"][seat]]

        for seat, name in enumerate(self.players):
            x, y = self.around(seat, *SEATS)
            status = now["status"][seat]
            cards = hand["hole_cards"][seat]
            faded = status in ("folded", "out")

            if cards and status != "out":
                brightness = lerp(110 if before["status"][seat] == "folded" else 255, 110 if status == "folded" else 255, amount)

                for index, code in enumerate(cards):
                    # On the first frame of a hand the cards are dealt out from the middle of the table
                    arrived = ease(moved * 2 - 0.8 * (dealing.index(seat) * 2 + index) / (len(dealing) * 2)) if self.frame == 0 else 1.0
                    target = (x - 63 + index * 54, y - 75)
                    self.draw_card(code, lerp(CENTRE[0] - CARD_WIDTH / 2, target[0], arrived), lerp(BOARD_Y, target[1], arrived), brightness, min(1.0, arrived * 4))

            plate = rl.Rectangle(x - 80, y + 5, 160, 54)
            rl.draw_rectangle_rounded(plate, 0.3, 8, self.PLATE)

            if seat in winners:
                rl.draw_rectangle_rounded_lines_ex(plate, 0.3, 8, 3, self.GOLD)
            elif now["seat"] == seat:
                rl.draw_rectangle_rounded_lines_ex(plate, 0.3, 8, 2, self.TEXT)
            else:
                rl.draw_rectangle_rounded_lines_ex(plate, 0.3, 8, 1, self.LINE)

            # The dealer button and the blinds are marked in the corner of the plate
            marks = 150

            if cards and seat == hand["button"]:
                rl.draw_circle(int(plate.x) + 142, int(plate.y) + 16, 9, self.TEXT)
                self.draw_text_centred("D", int(plate.x) + 143, int(plate.y) + 12, 10, self.BACKGROUND)
                marks -= 24

            blind = "SB" if seat == hand["small_blind"] else "BB" if seat == hand["big_blind"] else ""

            if cards and blind:
                self.draw_text_right(blind, int(plate.x) + marks, int(plate.y) + 12, 10, self.MUTED)
                marks -= 20

            rl.draw_circle(int(plate.x) + 15, int(plate.y) + 16, 5, rl.fade(self.PLAYER_COLOURS[seat], 0.4 if faded else 1.0))
            rl.draw_text(self.fit(name, 20, marks - 31), int(plate.x) + 27, int(plate.y) + 7, 20, self.MUTED if faded else self.TEXT)

            chips = round(lerp(before["stacks"][seat], now["stacks"][seat], amount))
            rl.draw_text(f"{chips:,}", int(plate.x) + 12, int(plate.y) + 30, 20, self.MUTED if faded else self.SOFT)

            # A badge over the bottom of their cards says what this player last did, or what they showed down.
            # It pops up brightly as they do it, and then stays there dimmed until the next round of betting.
            did = {"out": "Out", "all in": "All in", "folded": "Fold"}.get(status, "")
            fresh = raised = problem = False

            if seat in now["winners"] and showdown is None:
                did, fresh = "Wins", True

            elif showdown is not None and self.frame >= showdown and hand["ranks"][seat] and status != "out":
                did = hand["ranks"][seat]

            else:
                for index in range(self.frame, -1, -1):
                    other = hand["frames"][index]

                    if other["kind"] in ("street", "showdown"):
                        break

                    if other["seat"] == seat and other["label"]:
                        if status == "in" or index == self.frame:
                            did, fresh, raised, problem = other["label"], index == self.frame, other["kind"] == "raise", bool(other["problem"])

                        break

            if did:
                self.draw_badge(did, x, y - 10, bright=fresh, gold=raised and fresh or seat in winners, muted=faded, warned=problem, arrived=amount if fresh else 1.0)

    def prepare(self, hand: dict):
        # Works out the lines of the log for a hand, and which chips are in the pot after each thing that happens in it
        self.prepared_hand = self.hand
        self.log_lines = []
        self.pot_chips = []

        chips: dict[int, int] = {}
        bets = [0] * len(self.players)
        held = 0

        for index, frame in enumerate(hand["frames"]):
            self.log_lines += [(index, frame["kind"], line) for line in self.wrap(frame["text"], 20, WIDTH - TABLE_WIDTH - 32)]

            if frame["problem"]:
                self.log_lines += [(index, "problem", line) for line in self.wrap(f"! Default action used: {frame['problem']}", 10, WIDTH - TABLE_WIDTH - 32)]

            if frame["kind"] == "ante":
                for was, left in zip(hand["frames"][index - 1]["stacks"], frame["stacks"]):
                    for kind, count in self.chips_for(was - left):
                        chips[kind] = chips.get(kind, 0) + count

            elif frame["kind"] == "win":
                # Whoever wins takes their share of every kind of chip
                left = self.held(frame)
                chips = {kind: -(-count * left // held) for kind, count in chips.items()} if left else {}
            else:
                # The pot keeps the same chips which were bet into it, so that they can be followed across the table
                for seat, (was, bet) in enumerate(zip(bets, frame["bets"])):
                    if bet < was and not (frame["kind"] == "return" and frame["seat"] == seat):
                        for kind, count in self.chips_for(was - bet):
                            chips[kind] = chips.get(kind, 0) + count

            bets = frame["bets"]
            held = self.held(frame)
            self.pot_chips.append(dict(chips))

    def held(self, frame: dict) -> int:
        # The chips in the middle of the table, which doesn't count the bets still in front of the players
        return frame["pot"] - sum(frame["bets"])

    def draw_chips(self, before: dict, now: dict, amount: float):
        winner = self.around(now["winners"][0], *SEATS) if now["kind"] == "win" else None

        for seat in range(len(self.players)):
            was, bet = before["bets"][seat], now["bets"][seat]
            home = self.around(seat, *SEATS)
            spot = self.bet_spot(seat)

            if bet > was:
                # Chips slide out from the player to join their bet. The number counts up, but the chips are the final ones from the start.
                x, y = (lerp(home[0], spot[0], amount), lerp(home[1], spot[1], amount)) if was == 0 else spot
                self.draw_pill(f"{round(lerp(was, bet, amount)):,}", x, y, min(1.0, amount * 3) if was == 0 else 1.0, self.chips_for(bet))

            elif bet > 0:
                self.draw_pill(f"{bet:,}", spot[0], spot[1], 1.0, self.chips_for(bet))

            if bet < was and amount < 1:
                # Chips which nobody called go back to the player. The rest are pushed into the pot, or straight to the winner if the hand is over.
                target = home if now["kind"] == "return" and now["seat"] == seat else winner or POT
                self.draw_pill(f"{was - bet:,}", lerp(spot[0], target[0], amount), lerp(spot[1], target[1], amount), 1 - amount ** 3, self.chips_for(was - bet))

        if now["kind"] == "ante" and amount < 1:
            for seat in range(len(self.players)):
                home = self.around(seat, *SEATS)
                paid = before["stacks"][seat] - now["stacks"][seat]

                if paid > 0:
                    self.draw_pill(f"{paid:,}", lerp(home[0], POT[0], amount), lerp(home[1], POT[1], amount), 1 - amount ** 3, self.chips_for(paid))

        # Chips on their way to the pot only join it once they get there, and chips which have been won leave it straight away
        pot_before = self.pot_chips[self.frame - 1] if self.frame > 0 else {}
        pot_now = self.pot_chips[self.frame]
        settled = amount >= 1 or now["kind"] == "win"
        in_pot = pot_now if settled else pot_before
        value = self.held(now) if settled else self.held(before)

        if value > 0 or in_pot:
            self.draw_pill(f"Pot {value:,}", POT[0], POT[1], 1.0, sorted(in_pot.items()))

        if now["kind"] == "win" and amount < 1:
            leaving = {kind: count - pot_now.get(kind, 0) for kind, count in pot_before.items() if count > pot_now.get(kind, 0)}

            for seat in now["winners"] if leaving else []:
                home = self.around(seat, *SEATS)
                share = sorted((kind, max(1, count // len(now["winners"]))) for kind, count in leaving.items())
                self.draw_pill(f"+{now['stacks'][seat] - before['stacks'][seat]:,}", lerp(POT[0], home[0], amount), lerp(POT[1], home[1], amount), 1 - amount ** 3, share)

    def draw_panel(self, hand: dict | None, now: dict | None):
        left, right = TABLE_WIDTH + 16, WIDTH - 16
        rl.draw_rectangle(TABLE_WIDTH, 0, WIDTH - TABLE_WIDTH, HEIGHT, self.PANEL)
        rl.draw_line(TABLE_WIDTH, 0, TABLE_WIDTH, HEIGHT, self.LINE)

        rl.draw_text("CHIPS", left, 16, 10, self.MUTED)
        y = 34

        for seat, name in enumerate(self.players):
            chips = now["stacks"][seat] if now else None
            colour = self.MUTED if chips == 0 else self.TEXT
            rl.draw_circle(left + 5, y + 9, 5, rl.fade(self.PLAYER_COLOURS[seat], 0.4 if chips == 0 else 1.0))
            rl.draw_text(self.fit(name, 20, 150), left + 18, y, 20, colour)

            if chips is not None:
                self.draw_text_right(f"{chips:,}", right, y, 20, colour)

            y += 24

        if hand is None:
            return

        y += 14
        rl.draw_text(f"HAND {hand['number']} OF {self.total_hands}", left, y, 10, self.MUTED)
        self.draw_text_right(f"BLINDS {hand['blinds'][0]}/{hand['blinds'][1]}" + (f"   ANTE {hand['ante']}" if hand["ante"] else ""), right, y, 10, self.MUTED)
        y += 18

        # The newest lines stay in view, and older ones scroll off the top
        shown = [line for line in self.log_lines if line[0] <= self.frame]
        heights = [14 if kind == "problem" else 22 for _, kind, _ in shown]

        while sum(heights) > HEIGHT - 16 - y:
            oldest = shown[0][0]

            while shown[0][0] == oldest:
                shown.pop(0)
                heights.pop(0)

        for (index, kind, line), height in zip(shown, heights):
            if kind == "problem":
                rl.draw_text(line, left, y, 10, self.WARNING)
            else:
                rl.draw_text(line, left, y, 20, self.TEXT if index == self.frame else self.MUTED if kind in ("street", "showdown", "deal") else self.SOFT)

            y += height

    def draw_footer(self):
        rl.draw_text(CONTROLS, 24, 692, 10, self.MUTED)
        state = "PAUSED" if self.paused else f"{SPEEDS[self.speed]:g}x"
        self.draw_text_right(state, TABLE_WIDTH - 24, 687, 20, self.WARNING if self.paused else self.SOFT)

    def draw_match_over(self, now: dict):
        rl.draw_rectangle(0, 0, TABLE_WIDTH, HEIGHT, rl.Color(0, 0, 0, 170))

        most = max(now["stacks"])
        leaders = [name for name, chips in zip(self.players, now["stacks"]) if chips == most]
        result = f"{leaders[0]} wins with {most:,} chips" if len(leaders) == 1 else f"{' and '.join(leaders)} tie on {most:,} chips"

        self.draw_text_centred("MATCH OVER", TABLE_WIDTH // 2, 240, 60, self.TEXT)
        self.draw_text_centred(self.fit(result, 30, TABLE_WIDTH - 80), TABLE_WIDTH // 2, 320, 30, self.GOLD)
        self.draw_text_centred("Press R to restart", TABLE_WIDTH // 2, 380, 20, self.TEXT)
        self.draw_text_centred("Press ESC to quit", TABLE_WIDTH // 2, 410, 20, self.SOFT)

    # ---- Helpers

    def around(self, seat: int, x: float, y: float) -> tuple[float, float]:
        angle = math.pi / 2 + seat * 2 * math.pi / len(self.players)  # Seat 0 is at the bottom, and play goes clockwise
        return CENTRE[0] + x * math.cos(angle), CENTRE[1] + y * math.sin(angle)

    def bet_spot(self, seat: int) -> tuple[float, float]:
        angle = math.pi / 2 + seat * 2 * math.pi / len(self.players)
        across = math.copysign(abs(math.cos(angle)) ** BETS_SHAPE[0], math.cos(angle))
        down = math.copysign(abs(math.sin(angle)) ** BETS_SHAPE[1], math.sin(angle)) if abs(math.sin(angle)) > 1e-9 else 0.0
        return BETS_CENTRE[0] + BETS[0] * across, BETS_CENTRE[1] + BETS[1] * down

    def draw_card(self, code: str, x: float, y: float, brightness: float, opacity: float):
        source = rl.Rectangle(48 * TEXTURE_ZOOM * RANKS.index(code[0]), 64 * TEXTURE_ZOOM * SUIT_ROWS[code[1]], 48 * TEXTURE_ZOOM, 64 * TEXTURE_ZOOM)
        tint = rl.Color(int(brightness), int(brightness), int(brightness), int(255 * opacity))
        rl.draw_texture_pro(self.cards, source, rl.Rectangle(round(x), round(y), CARD_WIDTH, CARD_HEIGHT), rl.Vector2(0, 0), 0, tint)

    def chips_for(self, amount: int) -> list[tuple[int, int]]:
        # The chips which are shown for an amount: its two biggest kinds of chip, as their place in CHIPS and how many of them
        kinds = []

        for kind, (value, _, _) in enumerate(CHIPS):
            count, amount = divmod(amount, value)

            if count:
                kinds.append((kind, count))

        return kinds[:2]

    def draw_pill(self, text: str, x: float, y: float, opacity: float, chips: list[tuple[int, int]] = ()):
        # A number on a dark background, with chips stacked up to the left of it. The more chips of a kind, the taller its stack.
        chips_width = CHIP_WIDTH + CHIP_SPACING * (len(chips) - 1) + 4 if chips else 0
        text_width = rl.measure_text(text, 20) + 16
        left = int(x - (chips_width + text_width) / 2)

        for index, (kind, count) in enumerate(chips):
            _, row, half = CHIPS[kind]
            height = 0 if count == 1 else 1 if count <= 3 else 2 if count <= 7 else 3
            source = rl.Rectangle(48 * TEXTURE_ZOOM * (4 * half + height), 48 * TEXTURE_ZOOM * row, 32 * TEXTURE_ZOOM, 48 * TEXTURE_ZOOM)
            rl.draw_texture_pro(self.chips, source, rl.Rectangle(left + CHIP_SPACING * index, int(y) + 16 - CHIP_HEIGHT, CHIP_WIDTH, CHIP_HEIGHT), rl.Vector2(0, 0), 0, rl.fade(self.TEXT, opacity))

        rl.draw_rectangle_rounded(rl.Rectangle(left + chips_width, int(y) - 14, text_width, 28), 1.0, 12, rl.Color(0, 0, 0, int(105 * opacity)))
        rl.draw_text(text, left + chips_width + 8, int(y) - 9, 20, rl.fade(self.TEXT, opacity))

    def draw_badge(self, text: str, x: float, y: float, *, bright: bool, gold: bool, muted: bool, warned: bool, arrived: float):
        width = rl.measure_text(text, 20) + 20
        box = rl.Rectangle(int(x - width / 2), int(y - 13 + 12 * (1 - arrived)), width, 26)

        if gold or bright:
            rl.draw_rectangle_rounded(box, 0.5, 8, rl.fade(self.GOLD if gold else self.TEXT, arrived))
        else:
            rl.draw_rectangle_rounded(box, 0.5, 8, rl.Color(0, 0, 0, 200))

        if warned:
            rl.draw_rectangle_rounded_lines_ex(box, 0.5, 8, 2, rl.fade(self.WARNING, arrived))  # The player's AI went wrong, and this was played for it

        colour = self.BACKGROUND if gold or bright else self.MUTED if muted else self.TEXT
        rl.draw_text(text, int(box.x) + 10, int(box.y) + 4, 20, rl.fade(colour, arrived))

    def draw_text_centred(self, text: str, x: int, y: int, size: int, colour: rl.Color):
        rl.draw_text(text, x - rl.measure_text(text, size) // 2, y, size, colour)

    def draw_text_right(self, text: str, x: int, y: int, size: int, colour: rl.Color):
        rl.draw_text(text, x - rl.measure_text(text, size), y, size, colour)

    def fit(self, text: str, size: int, width: int) -> str:
        text = text.encode("ascii", "replace").decode()

        if rl.measure_text(text, size) <= width:
            return text

        while text and rl.measure_text(text + "..", size) > width:
            text = text[:-1]

        return text + ".."

    def wrap(self, text: str, size: int, width: int) -> list[str]:
        lines = [""]

        for word in text.encode("ascii", "replace").decode().split():
            longer = f"{lines[-1]} {word}".strip()

            if rl.measure_text(longer, size) <= width or not lines[-1]:
                lines[-1] = self.fit(longer, size, width)
            else:
                lines.append(self.fit(word, size, width))

        return lines
