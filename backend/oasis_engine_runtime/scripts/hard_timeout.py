from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable
from typing import TypeVar


T = TypeVar("T")


class HardOperationTimeout(TimeoutError):
    pass


async def run_with_hard_timeout(
    operation: Awaitable[T], *, timeout_seconds: float, cleanup_grace_seconds: float,
    platform: str, phase: str, round_num: int | None = None,
) -> T:
    task = asyncio.create_task(operation)
    done, _ = await asyncio.wait({task}, timeout=timeout_seconds)
    if task in done:
        return task.result()

    task.cancel()
    await asyncio.wait({task}, timeout=cleanup_grace_seconds)
    location = f"{platform} {phase}"
    if round_num is not None:
        location += f" round {round_num}"
    error = HardOperationTimeout(
        f"OASIS {location} timed out after {timeout_seconds:g}s; "
        f"cancellation grace {cleanup_grace_seconds:g}s expired"
    )
    # This runner owns a dedicated child process. Raising would let asyncio.run()
    # wait forever while cancelling a third-party task that ignores cancellation.
    print(f"Fatal timeout: {error}", file=sys.stderr, flush=True)
    os._exit(2)
