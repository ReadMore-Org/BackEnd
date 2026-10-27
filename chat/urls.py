from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MessageFileView, RoomViewSet

router = SimpleRouter()
router.register("rooms", RoomViewSet, basename="chat-room")

urlpatterns = [
    *router.urls,
    path(
        "messages/<int:pk>/file/", MessageFileView.as_view(), name="chat-message-file"
    ),
]
