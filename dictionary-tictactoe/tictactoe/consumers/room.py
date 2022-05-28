from typing import List

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from tictactoe.game import Game, GameStateEnum, GameTasks, PlayerState, RoomState

game_states = {}


class RoomConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_group_name = f"room_{self.scope['url_route']['kwargs']['room_id']}"
        # if there is a game_state on websocket connect,
        # try getting the game state
        game_state: Game = game_states.get(self.room_group_name, None)
        if not game_state:
            # if no game state is present, (you're the first to join the room)
            # create a new game state
            game_state = Game(
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

        if game_state.room_state == RoomState.GAME_START:
            # send the initial game state to players if the game is started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "start_game",
                    "message": game_state.to_json(),
                },
            )
            game_state.change_room_state(RoomState.GAME_IN_PROGRESS)
            game_state.create_task(GameTasks.PALETTE_TASK)

    async def disconnect(self, close_code):
        game_state: Game = game_states[self.room_group_name]
        game_state.remove_player(self.channel_name)
        # if we remove both players, room_state becomes GAME_ABORTED
        if game_state.room_state == RoomState.GAME_ABORTED:
            # if the game ends this way, delete the game from our
            # game dictionary
            del game_states[self.room_group_name]
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # this function receives messages from the client
    # payload is a python dictionary
    async def receive_json(self, payload: dict):

        game_state: Game = game_states[self.room_group_name]
        msg_type = int(payload["type"])
        if (
            msg_type == GameStateEnum.GAME_STATE_SYNC
            and game_state.room_state == RoomState.GAME_IN_PROGRESS
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

        elif msg_type == PlayerState.STEAL_PALETTE:
            victim = game_state.get_player(payload["player"])
            thief = game_state.get_player(self.channel_name)
            if game_state.steal_palette(thief, victim):
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "notify_palette_change",
                        "players": self.get_players(),
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
                "message": {"text": payload["message"]["game_data"]},
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
                "message": payload,
            },
        )
