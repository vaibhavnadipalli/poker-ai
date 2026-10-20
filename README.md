# ♠️ Warwick AI Poker Competition 🏆

### 🎮 **Welcome to the second WAI AI Programming Competition!** 🎮

<!--[![Competition Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://warwick.ai)-->
<!--[![Week](https://img.shields.io/badge/Deadline-Week%209%20Term%201-orange)](https://warwick.ai)-->
<!--[![Prize](https://img.shields.io/badge/Prize-£50%20Tesco%20Voucher-gold)](https://warwick.ai)-->

</div>

---

Hello all and welcome to the second Warwick AI programming competition!

Don't worry if you're new to programming or AI, there's something here for everyone! For beginners, check out the WAI + Code Soc + UWCS Python course or ask us anything at our weekly code nights. See our [website](https://warwick.ai) for details.

> [!IMPORTANT]
> ### Please only change `myAI.py`
> Your whole bot should be in `myAI.py`, and please don't edit, add, rename, move or delete any other file in your repository. That includes the `poker` folder, the `examples` folder, `pyproject.toml`, `README.md` and the `.github` folder. Every bot is played with the same copy of these files, so changing them can stop yours from working.
>
> If you have an idea for the game itself, we'd love to hear it (see [Contributing](#-contributing)).

### 🎯 Competition Highlights

- **Format:** Squad up in teams of any size!
- **Duration:** Running officially till week 10 of term 1
- **Prize:** The winning team will receive whatever Sam says they will + eternal WAI glory
- **Leaderboard:** Live updates on our website throughout the competition
- **Final Testing:** We'll do thorough testing for final results

### 📝 Contributing

We want this repository to become place where future members can explore a variety of AI implementations and archetypes. 

Once the competition is over, we'd love to accept any and all creations as open source contributions! Your AI might even be used as a baseline for scoring future submissions!

Also, this is a also new project with room for improvement. If you have ideas or suggestions:
- Message us directly
- Send a pull request with your changes to the main competition repository, not to your own submission

Open source contributions are great practice and go an long way on a CV!

## 🛠️ Environment Setup

### Using the Template

### Step 1 - Login on our Website
First, login on our website https://warwick.ai with your GitHub account!  Don't worry if you forget, logging in later won't break anything :)

### Step 2 - Copy the Template
Next, use this template repository to create you own by pressing `Use this template`<!--:      ⬇️-->

<!-- <img width="904" height="72" alt="template" src="https://github.com/user-attachments/assets/b05ccea8-bb53-4eed-ad5a-2de0b3a15b1d" /> -->

This button is in the top right of the page. You will be prompted to give it a name and choose for it to be public/private. These setting are completely up to you and won't affect anything :)

### Step 3 - Enable the WAI GitHub App
Then, go to https://github.com/apps/warwickai and press install/configure to authorise the app to view your repository.

This is what allows us to send your score to the leaderboard!

<img width="452" height="170" alt="ghapp" src="https://github.com/user-attachments/assets/952fad17-b664-457f-982b-50cb5e42896a" />

### Step 4 - Installing Dependencies
Open your project's repository in a terminal and install the required dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

With this done, submitting is as easy as pushing a commit to your repository!

### Alternatives
If you don't have a development environment set up, an alternative is making a github codespace:

<img width="452" height="431" alt="codespaces" src="https://github.com/user-attachments/assets/750288fb-c6ad-4602-9f36-08f53f8eaed2" />

Please note, command line tools will not work from a github codespace, instead the code must be run locally.

---

## 🎯 Running the Game

Installing the project gives you a `poker` command, which plays AIs against each other. An AI is any python file with a `myAI` function, and there are a few simple ones to play against in the `examples` folder. At least 2 AIs can play. More than 8 are split between tables, and `poker run` opens a window for each table. The game is played by the [Tournament Rules](#-tournament-rules) below. When it ends, poker prints where everyone finished, the hand (and table) on which each player went out, and everyone's score.

The bots in the `examples` folder each follow one simple rule. A rule never changes as the flop, turn and river are dealt:

| Bot | Rule |
|---|---|
| `default.py` | Checks when there is nothing to call, and folds to any bet. This is also what is played for any bot which makes an invalid move |
| `call.py` | Calls every bet |
| `call_preflop.py` | Calls before the flop, then checks or folds |
| `call_when_big_blind.py` | Calls any bet when it is the big blind, and otherwise checks or folds |
| `call_when_blind.py` | Calls any bet when it is the small blind or the big blind, and otherwise checks or folds |
| `raise_by_big_blind_unless_raised.py` | Raises by at least the minimum raise whenever nobody has bet more than the big blind, and folds to anything bigger |
| `raise_by_half_of_stack.py` | Raises by half of the chips it has left after calling, or the minimum raise if that is bigger |
| `raise_by_pot.py` | Raises by the size of the pot, or the minimum raise if that is bigger |
| `raise_by_pot_when_biggest_stack.py` | Raises by the size of the pot, or the minimum raise if that is bigger, when it has the most chips at the table, and otherwise checks or folds |
| `go_all_in.py` | Goes all in every time |
| `go_all_in_on_pair.py` | Goes all in when its two cards are a pair, and otherwise checks or folds |
| `go_all_in_on_ace.py` | Goes all in when it holds an ace, and otherwise checks or folds |

#### 👀 Watch a match
```bash
poker run myAI.py examples/call.py examples/default.py
```

This opens a window and plays a match in it, showing everyone's cards, the bets and what each AI does. The window can be resized, and adding `--fullscreen` starts it filling the screen.

| Key | What it does |
|---|---|
| `SPACE` | Pause and resume |
| `LEFT` / `RIGHT` | Step backwards and forwards |
| `UP` / `DOWN` | Speed up and slow down |
| `N` | Skip to the next hand |
| `F` | Switch between a window and fullscreen |
| `R` | Restart the match |
| `ESC` | Quit |

#### ⚡ Run headless tests
```bash
poker test 100 myAI.py examples/call.py examples/raise_by_big_blind_unless_raised.py examples/default.py
```

This plays 100 matches without showing them, and prints how each AI did.

#### 🎲 Deterministic testing
```bash
poker run myAI.py examples/raise_by_big_blind_unless_raised.py --seed 123
poker test 100 myAI.py examples/raise_by_big_blind_unless_raised.py --seed 69
```

#### 🆚 Comparing versions of your AI
```bash
poker run new=myAI.py old=old/myAI.py examples/default.py
```

Writing `NAME=PATH` chooses the name an AI is shown with. Run `poker run --help` to see the other options, such as `--hands`, `--stack` and `--blinds`.

#### 🏅 Checking your score
```bash
poker score
```

This runs the same tests as when you push: it checks your AI returns an action, in time, on 1000 sample states. A bot which passes gets 100 points, which are printed and written to `score.txt`. All of your other points come from the weekly tournaments.

#### 📜 Trying different rules
```bash
poker run myAI.py examples/default.py --rules my_rules.yaml
```

The rules of a match, such as how many chips everyone starts with and how quickly the blinds go up, are in `poker/internals/rules.yaml`. To try different ones, copy that file, change the copy, and pass it with `--rules`. Your copy only needs the lines which are different.

---

## 🃏 Tournament Rules

These are the rules every game is played by, including the weekly competition. All of the numbers are set in `poker/internals/rules.yaml`.

### The Game

- The game is no-limit Texas hold'em.
- Everyone starts with **200 chips**, which is 100 big blinds.
- A player who has no chips left at the end of a hand is out.
- The game carries on until one player has every chip.

### Tables

- A table seats at most 8 players. With more than 8, players are dealt out in turn, in the order they are given, between as few tables as they fit at, so the tables are as even as they can be. In the weekly tournament, the order is drawn at random.
- The tables play **hand for hand**: no table deals its next hand until every other table has finished the one before. So hand 20 at one table is played alongside hand 20 at every other.
- Players are only moved between tables once every table has finished a hand.
  - **Breaking a table:** when everyone left would fit at fewer tables, the table with the fewest players is broken up, and its players are sent one at a time to whichever tables have the fewest players.
  - **Balancing:** when one table has two or more players more than another, the player who would be the next big blind at the bigger table moves to the smaller one.
- A player who moves sits down as the **next big blind** at their new table, so moving never lets anyone skip the blinds.

### Each Hand

- The dealer button starts at a random seat and moves on to the next player every hand. The two players after the button pay the small and big blinds. When only two players are left, the button pays the small blind.
- From the fourth level, everyone also pays an **ante** into the pot before the hand. An ante doesn't count towards calling a bet.
- **Betting and raising:** `Action.raise_by(amount)` calls the current bet and then raises it by `amount` more chips. The minimum bet and raise are one big blind. The small blind is the only exception to the minimum bet when posting the blind. If a bet or raise is bigger than the current minimum raise, that amount becomes the new minimum raise for the rest of the betting round. The minimum raise resets to one big blind at the start of each betting round: pre-flop, flop, turn and river. A raise below the minimum is rounded up to the minimum when the player can afford it; otherwise, the player goes all in for their remaining chips. A short all-in below the minimum does not change the minimum raise. A raise of more than you have puts you all in. If nobody left could call a raise, a raise counts as a call.
- **Calling** a bet bigger than your stack puts you all in.
- Any part of a bet which nobody called goes back to the player who made it. Side pots are made for players who are all in, and a split pot gives any odd chips to the first players after the button.

### Blinds and Antes

The blinds go up a level every **15 hands**, and every table is always on the same level. The ante is about an eighth of the big blind.

| Level | Hands | Blinds | Ante |
|---|---|---|---|
| 1 | 1–15 | 1/2 | – |
| 2 | 16–30 | 2/4 | – |
| 3 | 31–45 | 3/6 | – |
| 4 | 46–60 | 5/10 | 1 |
| 5 | 61–75 | 10/20 | 3 |
| 6 | 76–90 | 20/40 | 5 |
| 7 | 91–105 | 30/60 | 8 |
| 8 | 106–120 | 50/100 | 13 |
| 9 | 121–135 | 100/200 | 25 |
| 10 | 136–150 | 200/400 | 50 |

After that, the pattern carries on ten times bigger.

### Time Limits and Invalid Moves

- Your AI has **1 second** for each action.
- If it raises an exception, takes too long, doesn't return an `Action`, or checks when there is a bet to call, it checks if it can and folds if it can't. That is the same as `defaultAI` and `examples/default.py`, and it counts as a bad action.
- In the weekly tournament, every bot runs on its own, apart from the game, with no internet access, 512 MB of memory and one CPU. It can read the files in its repo but not change them, and what it prints isn't shown. A bot which can't be loaded checks or folds every time.

### Finishing Places

- The last player left wins.
- Everyone else finishes in the order they went out, the last to go out finishing highest.
- Players who go out on the same hand, at any table, are placed by how many chips they had at the start of that hand: more chips finishes higher.

### Tournament Score

Your score in a tournament is your **peak chips**, which is the most chips you ever had at the end of a hand, plus **bonus chips** for where you finished: 10 for last, 20 for second to last, and so on up to the winner.

- With 28 players, the winner ends with all 5,600 chips and scores 5,600 + 280 = **5,880**.
- Someone who never got past their starting stack of 200 scores 200 plus their bonus, so 210 if they came last.
- A tournament with more players has more chips in play, so it gives bigger scores.

Most of the score is for building a stack. A bot which folds every hand can outlast bots which gamble with each other, but it never wins a pot, so its peak chips stay at about its starting stack and it only gets the bonus for where it finished. The best way to score is to win chips, as in a real game of poker.

### Leaderboard Points

- **100 points** when you push a bot which passes the tests, which check it returns an action, in time, on 1000 sample states.
- Every weekly tournament then adds your **tournament score** to your total on the leaderboard.
- Your points add up from week to week, even when you push a new bot.
- Each week, your latest bot which passes the tests plays. If your newest push fails the tests, your last one which passed plays instead.

---

## 🧠 Writing Your AI

### The Basics
Your submission is the `myAI` function in `myAI.py`, and **`myAI.py` should be the only file you change**. Please put everything your bot needs, including any helper functions, in `myAI.py`:

```python
def myAI(state: GameState) -> Action:
    # Your bot goes here!
    return defaultAI(state)
```

Your AI function should use the current state of the game `state` and output an `Action` of type of `CHECK`, `CALL`, `RAISE` or `FOLD`·
These can be constructed using `Action.check()`, `Action.call()`, `Action.raise_by(amount: int)` or `Action.fold()`.

### What Your AI Sees

The game is played by the [Tournament Rules](#-tournament-rules) above. A few things about the `state` your AI is given:

- `chips_bet` is how many chips a player has put in during the current betting round, so the amount you need to call is the biggest `chips_bet` at the table minus your own. `chips_in_pot` is everything bet in the hand so far.
- `small_blind`, `big_blind` and `ante` are the sizes for the current hand, so your AI can size its bets as the blinds go up. `min_raise` is the minimum additional amount a bet or raise must be; it resets to `big_blind` each betting round and can increase during that round.

### Some Inspiration

There's all sorts of ways to write an AI for this competition:
- Rules/heuristics
- Search algorithms
- Reinforcement learning
- and much more!

---

## 🏆 Submitting your AI

To submit your AI, simply push a commit to your repository. 

> [!IMPORTANT]
> **Your commits should only change `myAI.py`.** Before you push, check that no other file has changed, for example with `git status`. If anything other than `myAI.py` is listed, undo the change with `git restore <file>`, or delete the file if you added it.

Every week at code night, your latest bot which passes the tests will compete against all other submitted bots. Your points add up from week to week, and you can see them on our website! <https://warwick.ai>

---

## 🗓️ Running the Weekly Tournament

This is for the organisers. Whenever this template changes, bring every team's repo up to date with the website's `db/push-template-updates.ts`, which also scores every bot again. It can't change `.github/workflows`, so check the repos it lists as having an out of date workflow.

Each week:

1. **Download every team's bot.** In the website folder, this picks each team's latest submission which passed the tests:
   ```bash
   PROJECT_ID=poker PICK=latest npx astro db execute db/download-snapshots.ts --remote
   ```
2. **Move the bots out of the website folder,** to keep them away from its credentials:
   ```bash
   mv snapshots/poker ~/poker-round-1
   ```
   If `~/poker-round-1` already exists, e.g. from downloading again, move or delete it first. Otherwise `mv` puts the new bots inside it, as `~/poker-round-1/poker`, and the tournament still plays the old ones.
3. **Check the bots and build the sandbox.** In the WarwickAI/competitions folder, with Docker running, this runs every team's tests again in a locked-down container of its own, and builds the `wai-results` image the tournament uses:
   ```bash
   STUDENT_FILES="myAI.py" ./results/run.sh ~/poker-round-1 ../poker-comp-update
   ```
4. **Play the tournament.** In this folder, with Docker running, first try a few hands, which should say that every bot is ready:
   ```bash
   poker run --snapshots ~/poker-round-1 --hands 5
   ```
   Then play it, with the round's seed so it can be played again the same way:
   ```bash
   poker run --snapshots ~/poker-round-1 --seed 1 --results round-1.json
   ```
   Every team's bot runs in a Docker container of its own, with no network and no access to your files, and only the game itself runs on your computer. What each bot prints is kept in `bot-logs`, up to 1 MB each. Never add `--no-sandbox` for the teams' bots, as it runs their code on your computer itself.
5. **Record the results.** In the website folder, check with a dry run first, then run it again without `DRY_RUN=1`:
   ```bash
   PROJECT_ID=poker ROUND=1 RESULTS=../poker-comp-update/round-1.json DRY_RUN=1 \
     npx astro db execute db/record-tournament.ts --remote
   ```

The leaderboard adds each team's tournament score to their total. Recording a round again replaces it, so a mistake can be fixed by recording the right results. A tournament which was stopped before it finished is only recorded with `FORCE=1`.

---

## Important!!!

> [!IMPORTANT]
> **Please only change `myAI.py`,** and put all of your code, including helper functions, in it.

Other than this, have fun and see you at code nights! 

---

### Need Help?
- Weekly code nights
- Visit [warwick.ai](https://warwick.ai)
- Message us with questions

### Credits
Thanks to [@FinlaySanders](https://github.com/FinlaySanders) for their work on the user interface, and to [@stmio](https://github.com/stmio) for the database integration.

The card and chip art is from the [(Pixel) Poker Cards](https://ivoryred.itch.io/pixel-poker-cards) pack by IvoryRed, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

<div align="center">

### 🏆 **Good luck and may the best bot win!** 🏆

</div>
