from django.conf import settings
from django.db import models


def pair_key_for(first_id, second_id):
    """Chave estável do par de usuários (a ordem dos ids não importa): '3:17'."""
    low, high = sorted((int(first_id), int(second_id)))

    return f"{low}:{high}"


class Room(models.Model):
    """Conversa privada entre exatamente duas pessoas.

    Existe no máximo uma por par de usuários (`pair_key` único) e só nasce pelo botão
    "Entrar em contato" de um anúncio do marketplace (ver chat/services.py: open_contact).
    """

    pair_key = models.CharField(max_length=41, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="Membership",
        related_name="chat_rooms",
        blank=True,
    )

    class Meta:
        verbose_name = "Conversa"
        verbose_name_plural = "Conversas"

    def __str__(self):
        return f"Conversa {self.pair_key}"


class Membership(models.Model):
    """Participação de um usuário em uma conversa: é a única fonte de autorização do chat."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="chat_memberships",
        on_delete=models.CASCADE,
    )
    room = models.ForeignKey(Room, related_name="memberships", on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_read_at = models.DateTimeField(null=True, blank=True)
    # Anúncio pelo qual este usuário abriu a conversa e que ainda não foi anexado a uma mensagem:
    # aparece como cartão acima do campo de texto e vai junto com a próxima mensagem enviada.
    pending_anuncio = models.ForeignKey(
        "core.Anuncio",
        related_name="+",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Participação"
        verbose_name_plural = "Participações"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "room"], name="chat_membership_unique_user_room"
            ),
        ]

    def __str__(self):
        return f"{self.user} em {self.room}"
