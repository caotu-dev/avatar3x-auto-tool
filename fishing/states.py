from enum import Enum, auto


class FishingState(Enum):
    IDLE = auto()
    OUT_OF_BAIT = auto()
    EXIT_CONFIRM = auto()
    UNKNOWN = auto()
    LOADING = auto()
    READY = auto()
    WAITING = auto()
    FISHING = auto()
    SUCCESS = auto()
    FAILED = auto()
    RESULT = auto()
