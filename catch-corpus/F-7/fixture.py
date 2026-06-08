from collections.abc import Callable

TimeSource = Callable[[], float]

__all__ = ["TimeSource_USER"]


def TimeSource_USER(ts: TimeSource) -> float:
    return ts()
