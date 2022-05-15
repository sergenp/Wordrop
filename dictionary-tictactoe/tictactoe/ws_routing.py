from django.urls import path

from .consumers import RoomConsumer

websocket_urlpatterns = [
    path("ws/room/<uuid:room_id>/", RoomConsumer.as_asgi()),
]
