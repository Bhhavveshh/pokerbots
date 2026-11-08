"""Competition entry point: official Discard Hold'em protocol 1.0."""

import sys

sys.dont_write_bytecode = True

from pokerbot.protocol import main


if __name__ == "__main__":
    main()
