import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from pokerbot.testing import run_opponent
run_opponent("tight")
