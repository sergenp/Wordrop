"""tictactoe-websocket URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from tictactoe.views import create_room, index, join_room, room

urlpatterns = [
    path("", index),
    path("room/<uuid:room_name>/", room),
    path("join-room/", join_room),
    path("join-room/<uuid:room_id>/", join_room),
    path("create-room", create_room),
    path("admin/", admin.site.urls),
]
