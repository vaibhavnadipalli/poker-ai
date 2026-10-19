# Scores myAI.py when it is pushed. The WarwickAI/competitions action runs this, and passes the score.txt it writes on to
# the website. The tests are in poker/internals/score.py, which `poker score` also runs.
from poker.internals.score import score

from myAI import myAI

score(myAI, "score.txt")
