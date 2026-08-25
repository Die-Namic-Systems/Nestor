"""Allow ``python -m nestor`` alongside the installed ``nestor`` console script."""
import sys

from nestor.cli import main

if __name__ == "__main__":
    sys.exit(main())
