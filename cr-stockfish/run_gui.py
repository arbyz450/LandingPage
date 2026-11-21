"""Entry point for the one-file Windows build: launches the dashboard."""
import sys

from crsf.__main__ import main

if __name__ == "__main__":
    sys.exit(main(["gui"] + sys.argv[1:]))
