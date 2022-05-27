import enum


class PlayerState(int, enum.Enum):
    JOINED = 0
    DISCONNECTED = 1
    PALETTE_LOCKED = 2


class RoomState(int, enum.Enum):
    IN_LOBBY = 10
    GAME_STARTED = 20
    GAME_IN_PROGRESS = 21
    GAME_ENDED = 30
    GAME_ABORTED = 40


class GameStateEnum(int, enum.Enum):
    GAME_STATE_SYNC = 100
    PALETTE_SYNC = 200


class GameTasks(int, enum.Enum):
    PALETTE_TASK = 1000
