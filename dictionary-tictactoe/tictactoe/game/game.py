from typing import List, Literal, Union

from tictactoe.util.matrix import create_grid, get_cols, get_rows
from tictactoe.util.palette import check_if_word, generate_random_palette

from .enums import RoomState
from .player import Player


class Game:
    def __init__(
        self,
        grid_size: int = 10,
        palette_change_cooldown: int = 10,
        palette_size: int = 10,
        word_size: int = 5,
        room_group_name: str = None,
    ) -> None:
        self.room_group_name = room_group_name
        self.word_size = word_size
        self.palette_size = palette_size
        self.grid_size = grid_size
        self.palette_change_cooldown = palette_change_cooldown
        self.game_state = create_grid(self.grid_size, self.grid_size)
        self.room_state = RoomState.IN_LOBBY
        self.players = []

    def to_json(self) -> dict:
        return {"game_state": self.game_state, "players": self.get_players()}

    def change_room_state(
        self,
        state: Literal[
            RoomState.IN_LOBBY,
            RoomState.GAME_IN_PROGRESS,
            RoomState.GAME_ENDED,
            RoomState.GAME_ABORTED,
        ],
    ) -> None:
        """Changes the self.room_state to state
        and cancels all tasks if roomstate changes to game aborted or ended

        Args:
            state (Literal[ RoomState.IN_LOBBY, RoomState.GAME_IN_PROGRESS, RoomState.GAME_ENDED, RoomState.GAME_ABORTED, ]): State of the room that you want to self.room_state to be in
        """
        self.room_state = state

    def reset_game_state(self) -> None:
        """Resets game state back to it's original state"""
        self.game_state = create_grid(self.grid_size, self.grid_size)

    def create_player(self, name: str) -> Player:
        """Create and adds the player to the player list and returns the added player dict

        Args:
            name (str): Player id for the newly created player

        Returns:
            Player: Added player
        """
        # don't add new players if the game is in progress
        if self.room_state == RoomState.GAME_IN_PROGRESS:
            return

        player = Player(name, generate_random_palette(self.palette_size))
        self.players.append(player)

        if len(self.players) == 2:
            self.change_room_state(RoomState.GAME_IN_PROGRESS)

        return player

    def remove_player(self, name: str) -> Union[Player, None]:
        """Removes given name from self.players list, and changes the room_state accordingly

        Args:
            name (str): Id of the player to remove
        Returns:
            Player: Removed player
        """
        if not (player := self.get_player(name)):
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

        rows = get_rows(self.game_state)
        cols = get_cols(self.game_state)

        for row in rows:
            for i in range(len(row)):
                # take wordsize by wordsize
                if i + self.word_size > len(row):
                    break
                word = "".join(row[i : i + self.word_size]).lower()
                if word and len(word) == self.word_size and check_if_word(word):
                    self.change_room_state(RoomState.GAME_ENDED)
                    return True

        for col in cols:
            for i in range(len(col)):
                # take wordsize by wordsize
                if i + self.word_size > len(col):
                    break
                word = "".join(col[i : i + self.word_size]).lower()
                if word and len(word) == self.word_size and check_if_word(word):
                    self.change_room_state(RoomState.GAME_ENDED)
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
        player: Player = self.get_player(player)
        # if there is something at the spot of the [x][y], return False
        if (
            not player
            or self.game_state[x][y]
            or not (letter in player.palette)
            or not player.can_play
        ):
            return False

        # else put the letter
        self.game_state[x][y] = letter
        return True

    def steal_palette(self, thief_name: str, victim_name: str) -> bool:
        thief = self.get_player(thief_name)
        victim = self.get_player(victim_name)

        if not thief or not victim or not thief.can_play:
            return False

        return thief.steal_palette(victim)
