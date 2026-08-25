"""Allow ``python -m nestor`` alongside the installed ``nestor`` console script."""
import sys

from nestor.cli import main

sys.exit(main())
