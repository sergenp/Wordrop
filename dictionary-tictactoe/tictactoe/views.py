from django.shortcuts import redirect, render

# Create your views here.


def index(request):
    return render(
        request,
        "index.html",
    )


def join_room(request, room_id=""):
    return render(request, "join-room.html", {"room_id": room_id})


def room(request, room_name):
    return render(request, "room.html", {"room_name": room_name})


def create_room(request):
    return redirect(room, room_name="abc")
