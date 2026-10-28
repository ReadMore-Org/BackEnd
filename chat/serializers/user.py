from django.contrib.auth import get_user_model
from rest_framework import serializers

FALLBACK_NAME = "Leitor"


def display_name(user):
    """Nome exibido no chat: o nome do perfil; sem ele, "Leitor" (nunca o e-mail)."""
    name = (getattr(user, "name", "") or "").strip()

    return name or FALLBACK_NAME


class ChatUserSerializer(serializers.ModelSerializer):
    """Identificação pública mínima de um usuário no chat (nunca expõe e-mail nem permissões)."""

    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ["id", "name", "avatar"]
        read_only_fields = fields

    def get_name(self, user) -> str:
        return display_name(user)

    def get_avatar(self, user) -> str | None:
        # Mesma regra do restante do ReadMore: foto enviada, senão a foto do Google.
        foto = user.foto

        if foto is not None and foto.file:
            return foto.file.url

        return user.google_picture or None
