from typing import List

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db.utils import IntegrityError
from tictactoe.game import GameStateEnum, PlayerState, RoomState
from tictactoe.helper import GameManagerMixin

# in memory game states, game state data is saved when the game ends or it starts


class RoomConsumer(GameManagerMixin, AsyncJsonWebsocketConsumer):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    async def connect(self):
        self.room_group_name = f"room_{self.scope['url_route']['kwargs']['room_id']}"
        # if there is a game_state on websocket connect,
        # try getting the game state
        try:
            game, _ = await self.get_or_create_game(self.room_group_name)
        except IntegrityError:
            await self.close()
            return

        # if the game state is ended, in progress or aborted, close the connection
        if game.room_state in [
            RoomState.GAME_ENDED,
            RoomState.GAME_IN_PROGRESS,
            RoomState.GAME_ABORTED,
        ]:
            await self.close()
            return

        # add the player
        player = await self.create_player(self.room_group_name, self.channel_name)

        # if the player is not created, disconnect the socket
        if not player:
            await self.close()
            return

        # Join room if player is successfully created
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send_json(
            {
                "type": PlayerState.JOINED,
                "message": {"player": player.name, "palette": player.palette},
            }
        )

        if game.room_state == RoomState.GAME_IN_PROGRESS:
            # send the initial game state to players if the game is in progress
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_game",
                    "message": game.to_json(),
                },
            )

        # TODO, being able to watch an ongoing game?

    async def disconnect(self, close_code):
        player, _ = await self.remove_player_from_game(self.room_group_name, self.channel_name)

        # if only one player leaves
        # send the group that channel_name is disconnected
        if player:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "notify_player_disconnected", "message": player.name},
            )
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # this function receives messages from the client
    # payload is a python dictionary
    async def receive_json(self, payload: dict):
        msg_type = int(payload["type"])

        match msg_type:
            case GameStateEnum.GAME_STATE_SYNC:
                can_continue = await self.can_game_continue(self.room_group_name, self.channel_name)
                if not can_continue:
                    return
                # send received message to room
                x, y, letter = int(payload["x"]), int(payload["y"]), payload["letter"]

                is_updated, is_finished, game_data = await self.update_game(
                    self.room_group_name, x, y, self.channel_name, letter
                )

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

            case PlayerState.STEAL_PALETTE:
                if await self.steal_palette(
                    self.room_group_name, self.channel_name, payload["player"]
                ):
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            "type": "notify_palette_change",
                            "players": await self.get_players(self.room_group_name),
                        },
                    )

    # Receive message from room group
    async def update_game_state(self, payload: dict):
        # this function will be called for every channel
        # this means anything put here will be called _TWICE_ for our game
        # better to update the game in receive_json function then send the updated game
        await self.send_json(
            {
                "type": GameStateEnum.GAME_STATE_SYNC,
                "message": payload["message"]["game_data"],
            }
        )

    async def start_game(self, payload: dict):
        await self.send_json(
            {
                "type": RoomState.GAME_START,
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

    async def notify_palette_change(self, payload: List[dict]):
        await self.send_json(
            {
                "type": GameStateEnum.PALETTE_SYNC,
                "message": payload["players"],
            },
        )

    async def notify_player_disconnected(self, payload: dict):
        await self.send_json(
            {
                "type": PlayerState.DISCONNECTED,
                "message": payload["message"],
            },
        )
