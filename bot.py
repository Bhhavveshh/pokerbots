"""Development entry point; official protocol integration is still required."""

import sys

sys.dont_write_bytecode = True

from pokerbot.protocol import main


if __name__ == "__main__":
    main()
