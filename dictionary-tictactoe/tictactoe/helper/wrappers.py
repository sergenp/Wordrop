from tictactoe.game import GameTasks, RoomState


def cancel_tasks_on_room_state_change(f):
    async def wrapper(self, *args, **kwargs):
        out = await f(self, *args, **kwargs)
        room_group_name = next((x for x in args if x.startswith("room_")), None)
        game = await self._get_game(room_group_name)
        if not game:
            return out

        if game.room_state in [RoomState.GAME_ABORTED, RoomState.GAME_ENDED]:
            await self._cancel_all_tasks()

        elif game.room_state == RoomState.IN_LOBBY:
            await self._cancel_task(GameTasks.PALETTE_TASK, room_group_name)

        return out

    return wrapper
