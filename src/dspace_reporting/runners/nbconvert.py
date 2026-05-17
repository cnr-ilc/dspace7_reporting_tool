"""Run nbconvert with Windows asyncio settings compatible with pyzmq."""

from __future__ import annotations

import asyncio
import sys

from nbconvert.nbconvertapp import main as nbconvert_main


def configure_event_loop_policy() -> None:
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> int:
    configure_event_loop_policy()
    return nbconvert_main()


if __name__ == "__main__":
    raise SystemExit(main())
