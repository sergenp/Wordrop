import enum
import json
from typing import Literal

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from tictactoe.util.matrix import create_empty_grid
from tictactoe.util.palette import generate_random_palette


class PlayerState(int, enum.Enum):
    JOINED = 0
    DISCONNECTED = 1


class RoomState(int, enum.Enum):
    IN_LOBBY = 10
    GAME_STARTED = 20
    GAME_IN_PROGRESS = 21
    GAME_ENDED = 30
    GAME_ABORTED = 40


class GameStateEnum(int, enum.Enum):
    GAME_STATE_SYNC = 100
    PALETTE_SYNC = 200


game_states = {}


class GameState:
    def __init__(self, **options) -> None:
        self.options = options
        self.game_state = create_empty_grid(
            self.options.get("grid_size", 10), self.options.get("grid_size", 10)
        )
        self.room_state = RoomState.IN_LOBBY
        self.players = []

    def to_json(self) -> dict:
        return self.__dict__

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

        Args:
            state (Literal[ RoomState.IN_LOBBY, RoomState.GAME_STARTED, RoomState.GAME_IN_PROGRESS, RoomState.GAME_ENDED, RoomState.GAME_ABORTED, ]): State of the room that you want to self.room_state to be in
        """
        self.room_state = state

    def reset_game_state(self):
        """Resets game state back to it's original state"""
        self.game_state = create_empty_grid(
            self.options.get("grid_size", 10), self.options.get("grid_size", 10)
        )

    def create_player(self, player_id: str) -> dict:
        """Create nad adds the player to the player list and returns the added player dict

        Args:
            player_id (str): Player id for the newly created player

        Returns:
            dict: Added player data
        """
        # don't add new players if the game is started
        if self.room_state == RoomState.GAME_STARTED:
            return

        player = {
            "player": player_id,
            "palette": generate_random_palette(self.options.get("palette_size", 10)),
        }
        self.players.append(player)

        if len(self.players) == 2:
            self.change_room_state(RoomState.GAME_STARTED)

        return player

    def remove_player(self, player_id: str) -> dict:
        """Removes given player_id from self.players list, and changes the room_state accordingly

        Args:
            player_id (str): Id of the player to remove
        Returns:
            dict: Removed player data
        """
        removed_player = next(x for x in self.players if player_id == x.get("player"))
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
        player = next(x for x in self.players if player == x.get("player"))
        # if there is something at the spot of the [x][y], return False
        if self.game_state[x][y] or not (letter in player["palette"]):
            return False

        # else put the letter
        self.game_state[x][y] = letter
        return True


class RoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_group_name = f"room_{self.scope['url_route']['kwargs']['room_id']}"
        # if there is a game_state on websocket connect,
        # try getting the game state
        game_state: GameState = game_states.get(self.room_group_name, None)
        if not game_state:
            # if no game state is present, (you're the first to join the room)
            # create a new game state
            game_state = GameState()
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
                "message": {"player": player["player"], "palette": player["palette"]},
            }
        )

        if game_state.room_state == RoomState.GAME_STARTED:
            # send the initial game state to players if the game is started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_game",
                    "message": {"text": game_state.to_json()},
                },
            )

    async def disconnect(self, close_code):
        game_state: GameState = game_states[self.room_group_name]
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
