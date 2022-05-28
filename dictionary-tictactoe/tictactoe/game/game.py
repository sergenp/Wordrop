import asyncio
from typing import List, Literal, Union

from tictactoe.util.matrix import create_grid, get_cols, get_rows
from tictactoe.util.palette import check_if_word, generate_random_palette

from .enums import GameTasks, RoomState
from .player import Player


class Game:
    def __init__(
        self,
        grid_size=10,
        palette_change_cooldown=100,
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
            while self.room_state == RoomState.GAME_IN_PROGRESS:
                await asyncio.sleep(self.palette_change_cooldown)
                for player in self.players:
                    player.reset_palette(generate_random_palette(self.palette_size))
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "notify_palette_change",
                        "players": self.get_players(),
                    },
                )
        except asyncio.CancelledError:
            return

    def change_room_state(
        self,
        state: Literal[
            RoomState.IN_LOBBY,
            RoomState.GAME_START,
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
            self.cancel_task(GameTasks.PALETTE_TASK)

    def reset_game_state(self):
        """Resets game state back to it's original state"""
        self.game_state = create_grid(self.grid_size, self.grid_size)

    def create_player(self, name: str) -> Player:
        """Create and adds the player to the player list and returns the added player dict

        Args:
            name (str): Player id for the newly created player

        Returns:
            Player: Added player
        """
        # don't add new players if the game is started
        if self.room_state == RoomState.GAME_START:
            return

        player = Player(name, generate_random_palette(self.palette_size))
        self.players.append(player)

        if len(self.players) == 2:
            self.change_room_state(RoomState.GAME_START)

        return player

    def remove_player(self, name: str) -> Player:
        """Removes given name from self.players list, and changes the room_state accordingly

        Args:
            name (str): Id of the player to remove
        Returns:
            Player: Removed player
        """
        player = self.get_player(name)

        if not player:
            return

        self.players.remove(player)

        if len(self.players) == 0:
            self.change_room_state(RoomState.GAME_ABORTED)
        else:
            # reset the game state and put the game state back in lobby
            # if a player is removed from the game
            # TODO: maybe not reset the game state and continue from there?
            self.change_room_state(RoomState.IN_LOBBY)
            self.reset_game_state()

        return player

    def get_player(self, name: str) -> Union[Player, None]:
        """Gets the player with given `name`

        Args:
            name (str): Player name

        Returns:
            Union[Player, None]: Player or None, based on the name
        """
        return next((x for x in self.players if name == x.name), None)

    def get_players(self) -> List[dict]:
        """Serializes and returns all the players as json list

        Returns:
            List[dict]: List of players
        """
        return [player.to_json() for player in self.players]

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
            x (int): x coordination of the 2x2 array that you wanna put your `letter` on
            y (int): y coordination of the 2x2 array that you wanna put your `letter` on
            player (str): player that's trying to update the game
            letter (str): player's letter
        Returns:
            bool: Returns True if game is updated successfully, False if not.
        """
        player = self.get_player(player)
        # if there is something at the spot of the [x][y], return False
        if not player or self.game_state[x][y] or not (letter in player.palette):
            return False

        # else put the letter
        self.game_state[x][y] = letter
        return True

    def create_task(self, task_type: Literal[GameTasks.PALETTE_TASK]) -> None:
        """Creates the task of given task_type

        Args:
            task_type (Literal[GameTasks.PALETTE_TASK]): Type of the tasks to create
        """
        if task_type == GameTasks.PALETTE_TASK:
            # loop = get_event_loop()
            palete_changer_task = asyncio.get_event_loop().create_task(self.palette_changer())
            self._tasks.append({"type": GameTasks.PALETTE_TASK, "task": palete_changer_task})

    def cancel_task(self, task_type: Literal[GameTasks.PALETTE_TASK]) -> None:
        """Cancels the task with given task_type

        Args:
            task_type (int): Type of the tasks to cancel
        """
        try:
            task_dict = next(x for x in self._tasks if task_type == x["type"])
            task_dict["task"].cancel()
        except StopIteration:
            return
