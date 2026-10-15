# ♠️ Warwick AI Poker Competition 🏆

### 🎮 **Welcome to the second WAI AI Programming Competition!** 🎮

<!--[![Competition Status](https://img.shields.io/badge/Status-Active-brightgreen)](https://warwick.ai)-->
<!--[![Week](https://img.shields.io/badge/Deadline-Week%209%20Term%201-orange)](https://warwick.ai)-->
<!--[![Prize](https://img.shields.io/badge/Prize-£50%20Tesco%20Voucher-gold)](https://warwick.ai)-->

</div>

---

Hello all and welcome to the second Warwick AI programming competition!

Don't worry if you're new to programming or AI, there's something here for everyone! For beginners, check out the WAI + Code Soc + UWCS Python course or ask us anything at our weekly code nights. See our [website](https://warwick.ai) for details.

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
- Send a pull request with your changes

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

Installing the project gives you a `poker` command, which plays AIs against each other. An AI is any python file with a `myAI` function, and there are a few simple ones to play against in the `bots` folder. Between 2 and 8 AIs can play.

#### 👀 Watch a match
```bash
poker run myAI.py bots/caller.py bots/tight.py
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
poker test 100 myAI.py bots/caller.py bots/chaos.py bots/tight.py
```

This plays 100 matches without showing them, and prints how each AI did.

#### 🎲 Deterministic testing
```bash
poker run myAI.py bots/chaos.py --seed 123
poker test 100 myAI.py bots/chaos.py --seed 69
```

#### 🆚 Comparing versions of your AI
```bash
poker run new=myAI.py old=old/myAI.py bots/tight.py
```

Writing `NAME=PATH` chooses the name an AI is shown with. Run `poker run --help` to see the other options, such as `--hands`, `--stack` and `--blinds`.

#### 📜 Trying different rules
```bash
poker run myAI.py bots/tight.py --rules my_rules.yaml
```

The rules of a match, such as how many chips everyone starts with and how quickly the blinds go up, are in `poker/rules.yaml`. To try different ones, copy that file, change the copy, and pass it with `--rules`. Your copy only needs the lines which are different.

---

## 🧠 Writing Your AI

### The Basics
Your submission is the `myAI` function in `myAI.py`:

```python
def myAI(state: GameState) -> Action:
    # Your bot goes here!
    return defaultAI(state)
```

Your AI function should use the current state of the game `state` and output an `Action` of type of `CHECK`, `CALL`, `RAISE` or `FOLD`·
These can be constructed using `Action.check()`, `Action.call()`, `Action.raise_by(amount: int)` or `Action.fold()`.

### The Rules

The game is no-limit Texas hold'em. Everyone starts a match with the same number of chips, and a player who runs out is out of the match.

As in a tournament, the blinds go up as the match goes on. They go up a level every 3 orbits, which is 3 hands for each player still in, and each level is between 25% and 50% more than the last: 10/20, 15/30, 20/40, 30/60, 40/80, 50/100, 75/150, 100/200 and so on.

All of these numbers are set in `poker/rules.yaml`, along with rules which are turned off to begin with, like antes.

- `chips_bet` is how many chips a player has put in during the current betting round, so the amount you need to call is the biggest `chips_bet` at the table minus your own. `chips_in_pot` is everything bet in the hand so far.
- `small_blind`, `big_blind` and `ante` are the sizes for the current hand, so your AI can size its bets as the blinds go up.
- `Action.raise_by(amount)` calls the current bet and then raises it by `amount` more. There is no minimum raise, and if it is more than you have then you go all in.
- `Action.call()` when you can't afford the bet puts you all in.
- If your AI raises an exception, takes too long, doesn't return an `Action` or checks when there is a bet to call, then it checks if it can and folds if it can't, the same as `defaultAI`.

### Some Inspiration

There's all sorts of ways to write an AI for this competition:
- Rules/heuristics
- Search algorithms
- Reinforcement learning
- and much more!

---

## 🏆 Submitting your AI

To submit your AI, simply push a commit to your repository. 

Every week at code night, your latest bot will compete against all other submitted bots. Points will be awarded, which you will be able to see on our website! <https://warwick.ai>

---

## Important!!!

Don't change anything in the poker folder!

Other than this, have fun and see you at code nights! 

---

### Need Help?
- Weekly code nights
- Visit [warwick.ai](https://warwick.ai)
- Message us with questions

### Credits
The card and chip art is from the [(Pixel) Poker Cards](https://ivoryred.itch.io/pixel-poker-cards) pack by IvoryRed, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

<div align="center">

### 🏆 **Good luck and may the best bot win!** 🏆

</div>
