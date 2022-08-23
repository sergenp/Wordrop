import asyncio
from typing import Callable, List, Literal, Tuple, Union

from channels.db import database_sync_to_async
from strenum import StrEnum
from tictactoe.game import Game, GameTasks, Player, RoomState
from tictactoe.models import GameModel, PlayerModel
from tictactoe.util.palette import generate_random_palette

from .wrappers import cancel_tasks_on_room_state_change

# TODO, maybe find a better way to store in-memory tasks and games?
# redis?
_games = {}
_tasks = []


class GameStatesEnum(StrEnum):
    GAME_STATE = "game_state"
    GAME_MODEL = "game_model"


class DBObjectsMixin:
    @database_sync_to_async
    def _add_player_model(self, game: GameModel, player: PlayerModel):
        game.players.add(player)

    @database_sync_to_async
    def _create_game_model(self, room_group_name: str, state: dict):
        return GameModel.objects.create(
            room_uuid=room_group_name.split("room_")[1], game_state=state
        )

    @database_sync_to_async
    def _create_player_model(self, player_name: str):
        return PlayerModel.objects.create(name=player_name)

    @database_sync_to_async
    def _get_game_model(self, room_group_name: str) -> Union[GameModel, None]:
        return GameModel.objects.filter(room_uuid=room_group_name.split("room_")[1]).first()

    @database_sync_to_async
    def _get_player_model(self, player_name: str) -> Union[GameModel, None]:
        return PlayerModel.objects.filter(name=player_name).first()

    @database_sync_to_async
    def _update_game_model(self, game_model: GameModel, game: Game) -> None:
        game_model.room_state = game.room_state
        game_model.game_state = game.game_state
        game_model.save()


class TaskHelperMixin:
    @classmethod
    def task(cls, func):
        async def wrapper(*args, **kwargs):
            res = None
            try:
                res = await func(*args, **kwargs)
            except asyncio.CancelledError:
                return
            finally:
                return res

        return wrapper

    async def _get_task(
        self, task_type: Literal[GameTasks.PALETTE_TASK], room_group_name: str
    ) -> Union[dict, None]:
        return next(
            (
                x
                for x in _tasks
                if task_type == x["type"] and room_group_name == x["room_group_name"]
            ),
            None,
        )

    async def _create_task(
        self, task_type: Literal[GameTasks.PALETTE_TASK], task_func: Callable, room_group_name: str
    ) -> None:
        """Creates the task of given task_type

        Args:
            task_type (Literal[GameTasks.PALETTE_TASK]): Type of the tasks to create
        """
        # see if there is already a task in _tasks, if there is no, need to create another
        if await self._get_task(task_type, room_group_name):
            return

        if task_type == GameTasks.PALETTE_TASK:
            palete_changer_task = asyncio.get_event_loop().create_task(task_func(room_group_name))
            _tasks.append(
                {
                    "type": GameTasks.PALETTE_TASK,
                    "task": palete_changer_task,
                    "room_group_name": room_group_name,
                }
            )

    async def _cancel_task(
        self, task_type: Literal[GameTasks.PALETTE_TASK], room_group_name: str
    ) -> None:
        """Cancels the task with given task_type

        Args:
            task_type (int): Type of the tasks to cancel
        """
        if task_dict := await self._get_task(task_type, room_group_name):
            cancelled = task_dict["task"].cancel()
            if cancelled:
                # if task is cancelled, delete the task from _tasks
                _tasks.remove(task_dict)

    async def _cancel_all_tasks(self):
        for task_dict in _tasks:
            cancelled = task_dict["task"].cancel()
            if cancelled:
                _tasks.remove(task_dict)


class GameManagerMixin(DBObjectsMixin, TaskHelperMixin):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def _add_game(self, room_group_name: str, game: Game, game_model: GameModel) -> None:
        _games[room_group_name] = {
            GameStatesEnum.GAME_STATE: game,
            GameStatesEnum.GAME_MODEL: game_model,
        }

    async def can_game_continue(self, room_group_name: str, player_name: str) -> bool:
        game = await self._get_game(room_group_name)
        return (
            game.room_state == RoomState.GAME_IN_PROGRESS and game.get_player(player_name).can_play
        )

    async def _create_game(self, room_group_name: str) -> Game:
        game = Game(room_group_name=room_group_name)
        game_model = await self._create_game_model(room_group_name, game.game_state)
        await self._add_game(room_group_name, game, game_model)
        return game, game_model

    async def create_player(self, room_group_name: str, player_name: str) -> Union[Player, None]:
        game = await self._get_game(room_group_name)
        if game.room_state not in [RoomState.IN_LOBBY, RoomState.GAME_ENDED]:
            return None

        player = game.create_player(player_name)
        player_model = await self._create_player_model(player_name)
        game_model = await self._get_game_model(room_group_name)
        await self._add_player_model(game_model, player_model)

        if game.room_state == RoomState.GAME_IN_PROGRESS:
            await self._create_task(GameTasks.PALETTE_TASK, self._palette_changer, room_group_name)

        return player

    async def _get_game(self, room_group_name: str) -> Union[Game, None]:
        return _games.get(room_group_name, {}).get(GameStatesEnum.GAME_STATE)

    async def get_or_create_game(self, room_group_name) -> Tuple[Game, GameModel]:
        game = await self._get_game(room_group_name)
        game_model = await self._get_game_model(room_group_name)

        if not game or not game_model:
            game, game_model = await self._create_game(room_group_name)

        return game, game_model

    async def get_players(self, room_group_name: str) -> List[dict]:
        game = await self._get_game(room_group_name)
        return game.get_players()

    @cancel_tasks_on_room_state_change
    async def remove_player_from_game(
        self, room_group_name: str, player_name: str
    ) -> Tuple[
        Union[Player, None],
        Literal[
            RoomState.IN_LOBBY,
            RoomState.GAME_IN_PROGRESS,
            RoomState.GAME_ENDED,
            RoomState.GAME_ABORTED,
        ],
    ]:
        game: Game = await self._get_game(room_group_name)
        if not game:
            return None, None

        player = game.remove_player(player_name)
        return player, game.room_state

    async def steal_palette(self, room_group_name: str, thief_name: str, victim_name: str):
        game = await self._get_game(room_group_name)
        return game.steal_palette(thief_name, victim_name)

    @cancel_tasks_on_room_state_change
    async def update_game(
        self, room_group_name, x, y, channel_name, letter
    ) -> Tuple[bool, bool, dict]:
        game = await self._get_game(room_group_name)
        is_updated = game.update_game(x, y, channel_name, letter)
        is_finished = game.check_for_game_finish()

        if is_finished:
            # save to the db if the game is finished
            game_model = await self._get_game_model(room_group_name)
            await self._update_game_model(game_model, game)

        return is_updated, is_finished, game.to_json()

    @TaskHelperMixin.task
    async def _palette_changer(self, room_group_name: str) -> None:
        game = await self._get_game(room_group_name)
        while game.room_state == RoomState.GAME_IN_PROGRESS:
            await asyncio.sleep(game.palette_change_cooldown)
            for player in game.players:
                player.reset_palette(generate_random_palette(game.palette_size))
            await self.channel_layer.group_send(
                game.room_group_name,
                {
                    "type": "notify_palette_change",
                    "players": game.get_players(),
                },
            )
