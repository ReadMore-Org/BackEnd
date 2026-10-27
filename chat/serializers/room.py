from rest_framework import serializers

from chat import services

from .message import MessageSerializer
from .user import FALLBACK_NAME, ChatUserSerializer


class ContactSerializer(serializers.Serializer):
    """Entrada de POST /chat/rooms/contact/: o anúncio sobre o qual a pessoa quer conversar."""

    anuncio = serializers.IntegerField(min_value=1)


class RoomSerializer(serializers.Serializer):
    """Resumo da conversa para quem a consulta. Espera uma conversa anotada por services.rooms_for.

    `name` e `image` são os do outro participante (como no WhatsApp); `other` traz também a presença.
    """

    id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    other = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    last_message_at = serializers.DateTimeField(read_only=True)
    unread = serializers.IntegerField(read_only=True)
    last_message = serializers.SerializerMethodField()
    pending_anuncio = serializers.SerializerMethodField()

    def get_name(self, room) -> str:
        other = getattr(room, "other", None)

        return ChatUserSerializer(other).data["name"] if other else FALLBACK_NAME

    def get_image(self, room) -> str | None:
        other = getattr(room, "other", None)

        return ChatUserSerializer(other).data["avatar"] if other else None

    def get_other(self, room) -> dict | None:
        other = getattr(room, "other", None)

        if other is None:
            return None

        presence = getattr(other, "chat_presence", None)
        last_seen = (
            serializers.DateTimeField().to_representation(presence.last_seen)
            if presence and presence.last_seen
            else None
        )

        return {
            **ChatUserSerializer(other).data,
            "online": bool(presence and presence.is_online),
            "last_seen": last_seen,
        }

    def get_last_message(self, room) -> dict | None:
        message = getattr(room, "last_message", None)

        if message is None:
            return None

        return MessageSerializer(message, context=self.context).data

    def get_pending_anuncio(self, room) -> dict | None:
        anuncio = getattr(room, "pending_anuncio_obj", None)

        return services.anuncio_card(anuncio) if anuncio is not None else None
