import asyncio
import time
from typing import Literal

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from tictactoe.consumers.enums import GameStateEnum, GameTasks, PlayerState, RoomState
from tictactoe.util.matrix import create_grid, get_cols, get_rows
from tictactoe.util.palette import check_if_word, generate_random_palette

game_states = {}


class Player:
    def __init__(self, name, palette, **options) -> None:
        self.name = name
        self.palette = palette
        self.can_play = True
        self.lock_timer = time.time()
        self.lock_amount = options.get("max_lock_amount", 2)
        self.lock_cooldown = options.get("lock_cooldown", 10)  # in seconds

    def __eq__(self, __o: object) -> bool:
        return __o.name == self.name

    def to_json(self) -> str:
        return {"name": self.name, "palette": self.palette}

    def add_to_palette(self, palette):
        self.palette += palette

    def reset_palette(self, palette=None):
        self.palette = palette

    def can_lock(self) -> bool:
        if self.lock_amount > 0 and self.lock_timer + self.lock_cooldown > time.time():
            self.lock_timer = time.time()
            self.lock_amount -= 1
            return True
        return False


class GameState:
    def __init__(
        self,
        grid_size=10,
        palette_change_cooldown=10,
        palette_size=10,
        word_size=5,
        room_group_name=None,
        channel_layer=None,
    ) -> None:
        self.room_group_name = room_group_name
        self.channel_layer = channel_layer
        self.word_size = word_size
        self.palette_size = palette_size
        self.grid_size = grid_size
        self.palette_change_cooldown = palette_change_cooldown
        self.game_state = create_grid(self.grid_size, self.grid_size)
        self.room_state = RoomState.IN_LOBBY
        self.players = []
        self._tasks = []

    def to_json(self) -> dict:
        return {"game_state": self.game_state}

    async def palette_changer(self):
        try:
            while True:
                if self.room_state in [
                    RoomState.GAME_ABORTED,
                    RoomState.GAME_ENDED,
                    RoomState.IN_LOBBY,
                ]:
                    break
                await asyncio.sleep(self.palette_change_cooldown)
                for player in self.players:
                    player.palette = generate_random_palette(self.palette_size)
                await self.channel_layer.group_send(
                    self.room_group_name, {"type": "notify_palette_change", "players": self.players}
                )
        except asyncio.CancelledError:
            return

    def change_room_state(
        self,
        state: Literal[
            RoomState.IN_LOBBY,
            RoomState.GAME_STARTED,
            RoomState.GAME_IN_PROGRESS,
            RoomState.GAME_ENDED,
            RoomState.GAME_ABORTED,
        ],
    ):
        """Changes the self.room_state to state
        and cancels all tasks if roomstate changes to game aborted or ended

        Args:
            state (Literal[ RoomState.IN_LOBBY, RoomState.GAME_STARTED, RoomState.GAME_IN_PROGRESS, RoomState.GAME_ENDED, RoomState.GAME_ABORTED, ]): State of the room that you want to self.room_state to be in
        """
        self.room_state = state

        if self.room_state in [RoomState.GAME_ABORTED, RoomState.GAME_ENDED]:
            # abort every task if game ends
            for task_dict in self._tasks:
                task_dict["task"].cancel()

        elif self.room_state == RoomState.IN_LOBBY:
            # abort the palette task
            self.stop_task(GameTasks.PALETTE_TASK)

    def reset_game_state(self):
        """Resets game state back to it's original state"""
        self.game_state = create_grid(self.grid_size, self.grid_size)

    def create_player(self, name: str) -> dict:
        """Create and adds the player to the player list and returns the added player dict

        Args:
            name (str): Player id for the newly created player

        Returns:
            dict: Added player data
        """
        # don't add new players if the game is started
        if self.room_state == RoomState.GAME_STARTED:
            return

        player = Player(name, generate_random_palette(self.palette_size))
        self.players.append(player)

        if len(self.players) == 2:
            self.change_room_state(RoomState.GAME_STARTED)

        return player

    def remove_player(self, name: str) -> dict:
        """Removes given name from self.players list, and changes the room_state accordingly

        Args:
            name (str): Id of the player to remove
        Returns:
            dict: Removed player data
        """
        try:
            removed_player = next(x for x in self.players if name == x.name)
        except StopIteration:
            return

        self.players.remove(removed_player)

        if len(self.players) == 0:
            self.change_room_state(RoomState.GAME_ABORTED)
        else:
            # reset the game state and put the game state back in lobby
            # if a player is removed from the game
            # TODO: maybe not reset the game state and continue from there?
            self.change_room_state(RoomState.IN_LOBBY)
            self.reset_game_state()

        return removed_player

    def check_for_game_finish(self) -> bool:
        """Checks if the game is over

        Returns:
            bool: Returns true if one of the diagonals, columns or rows have the same elements
        """
        # TODO: game end logic
        rows = get_rows(self.game_state)
        cols = get_cols(self.game_state)

        for row in rows:
            for i in range(len(row)):
                # take wordsize by wordsize
                if i + self.word_size > len(row):
                    break
                word = "".join(row[i : i + self.word_size]).lower()
                if word and len(word) == self.word_size and check_if_word(word):
                    return True

        for col in cols:
            for i in range(len(col)):
                # take wordsize by wordsize
                if i + self.word_size > len(col):
                    break
                word = "".join(col[i : i + self.word_size]).lower()
                if word and len(word) == self.word_size and check_if_word(word):
                    return True

        return False

    def update_game(self, x: int, y: int, player: str, letter: str) -> bool:
        """Updates the game state based on the coordinations

        Args:
            x (int): x coordination of the 2x2 array that you wanna put X or O in
            y (int): y coordination of the 2x2 array that you wanna put X or O in
            player (str): player that's trying to update the game
            letter (str) : player's letter
        Returns:
            bool: Returns True if game is updated successfully, False if not.
        """
        player = next(x for x in self.players if player == x.name)
        # if there is something at the spot of the [x][y], return False
        if self.game_state[x][y] or not (letter in player.palette):
            return False

        # else put the letter
        self.game_state[x][y] = letter
        return True

    def create_task(self, task_type: int):
        if task_type == GameTasks.PALETTE_TASK:
            # loop = get_event_loop()
            palete_changer_task = asyncio.get_event_loop().create_task(self.palette_changer())
            self._tasks.append({"type": GameTasks.PALETTE_TASK, "task": palete_changer_task})

    def stop_task(self, task_type: int):
        try:
            task_dict = next(x for x in self._tasks if task_type == x["type"])
            task_dict["task"].cancel()
        except StopIteration:
            return


class RoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_group_name = f"room_{self.scope['url_route']['kwargs']['room_id']}"
        # if there is a game_state on websocket connect,
        # try getting the game state
        game_state: GameState = game_states.get(self.room_group_name, None)
        if not game_state:
            # if no game state is present, (you're the first to join the room)
            # create a new game state
            game_state = GameState(
                room_group_name=self.room_group_name, channel_layer=self.channel_layer
            )
            game_states[self.room_group_name] = game_state

        if game_state.room_state not in [RoomState.IN_LOBBY, RoomState.GAME_ENDED]:
            # if the game is started or ended,
            # don't accept anymore connections to this room
            await self.close()
            return
        # add the player
        player = game_state.create_player(self.channel_name)
        # Join room if game is still in lobby
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send_json(
            {
                "type": PlayerState.JOINED,
                "message": {"player": player.name, "palette": player.palette},
            }
        )

        if game_state.room_state == RoomState.GAME_STARTED:
            game_state.create_task(GameTasks.PALETTE_TASK)
            # send the initial game state to players if the game is started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_game",
                    "message": game_state.to_json(),
                },
            )

    async def disconnect(self, close_code):
        game_state: GameState = game_states[self.room_group_name]
        # TODO: what if player is connected to the game, but not in the self.players list?
        # e.g. if 3rd player joins the game, his connection is not accepted therefore not in the players list
        # but if he disconnects, this function will still be called, and will throw a StopIteration error
        game_state.remove_player(self.channel_name)
        # if we remove both players, room_state becomes GAME_ABORTED
        if game_state.room_state == RoomState.GAME_ABORTED:
            # if the game ends this way, delete the game from our
            # game dictionary
            del game_states[self.room_group_name]
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # this function receives messages from the frontend
    # payload is a python dictionary
    async def receive_json(self, payload: dict):

        game_state: GameState = game_states[self.room_group_name]
        msg_type = int(payload["type"])
        if (
            msg_type == GameStateEnum.GAME_STATE_SYNC
            and game_state.room_state == RoomState.GAME_STARTED
        ):
            # send received message to room
            x, y, letter = int(payload["x"]), int(payload["y"]), payload["letter"]
            is_updated = game_state.update_game(x, y, self.channel_name, letter)
            is_finished = game_state.check_for_game_finish()
            game_data = game_state.to_json()

            if is_updated:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "update_game_state",
                        "message": {"game_data": game_data},
                    },
                )

            if is_finished:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "notify_game_ended",
                        "message": {"winner": self.channel_name},
                    },
                )
                game_state.change_room_state(RoomState.GAME_ENDED)

    # Receive message from room group
    async def update_game_state(self, payload: dict):
        # this function will be called for every channel
        # this means anything put here will be called _TWICE_ for our game
        # better to update the game in receive_json function then send the updated game
        await self.send_json(
            {
                "type": GameStateEnum.GAME_STATE_SYNC,
                "message": {"text": payload["message"]["game_data"]},
            }
        )

    async def start_game(self, payload: dict):
        await self.send_json(
            {
                "type": RoomState.GAME_STARTED,
                "message": payload["message"],
            },
        )

    async def notify_game_ended(self, payload: dict):
        await self.send_json(
            {
                "type": RoomState.GAME_ENDED,
                "message": payload["message"],
            },
        )

    async def notify_palette_change(self, payload: dict):
        print(payload)
        await self.send_json(
            {
                "type": GameStateEnum.PALETTE_SYNC,
                "message": [x.to_json() for x in payload["players"]],
            },
        )
