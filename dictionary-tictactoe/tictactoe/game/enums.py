import enum
from typing import List, Tuple


class BaseIntEnum(int, enum.Enum):
    @classmethod
    def choices(cls: "BaseIntEnum") -> List[Tuple[int, str]]:
        return [(key.value, key.name) for key in cls]


class PlayerState(BaseIntEnum):
    JOINED = 0
    DISCONNECTED = 1
    STEAL_PALETTE = 2


class RoomState(BaseIntEnum):
    IN_LOBBY = 10
    GAME_START = 20
    GAME_IN_PROGRESS = 21
    GAME_ENDED = 30
    GAME_ABORTED = 40


class GameStateEnum(BaseIntEnum):
    GAME_STATE_SYNC = 100
    PALETTE_SYNC = 200


class GameTasks(BaseIntEnum):
    PALETTE_TASK = 1000
