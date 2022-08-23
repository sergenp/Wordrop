from django.db import models

from tictactoe.game import RoomState

# Create your models here.


class PlayerModel(models.Model):
    name = models.CharField(unique=True, null=False, blank=False, max_length=100)


class GameModel(models.Model):
    room_uuid = models.UUIDField(primary_key=True)
    game_state = models.JSONField()
    players = models.ManyToManyField(PlayerModel)
    room_state = models.IntegerField(choices=RoomState.choices(), default=RoomState.IN_LOBBY)
