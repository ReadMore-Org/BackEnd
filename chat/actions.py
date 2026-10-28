"""Operações do chat = regra de negócio (services) + difusão em tempo real (realtime).

REST (views) e WebSocket (consumer) chamam estas mesmas funções, então os dois caminhos têm
exatamente a mesma validação, a mesma autorização e emitem os mesmos eventos.
Funções síncronas.
"""

from . import realtime, services

# ---- mensagens ----


def send_message(user, room, *, body=None, file=None, reply_to_id=None):
    message = services.send_message(
        user, room, body=body, file=file, reply_to_id=reply_to_id
    )
    realtime.broadcast_message_new(message)

    return message


def edit_message(user, room, message_id, body):
    message = services.edit_message(user, room, message_id, body)
    realtime.broadcast_message_update(message)

    return message


def delete_message(user, room, message_id):
    message = services.delete_message(user, room, message_id)
    realtime.broadcast_message_update(message)

    return message


def notify_typing(user, room):
    services.get_membership(user, room)
    realtime.broadcast_typing(user, room)


def mark_read(user, room):
    message_ids = services.mark_read(user, room)

    if message_ids:
        realtime.broadcast_read(room, message_ids)

    # Atualiza o contador (zerado) em todas as abas do leitor, mesmo sem ids novos.
    realtime.broadcast_room_changed(room.id, [user.pk])


# ---- conversas ----


def open_contact(user, anuncio_id):
    """Abre a conversa com o dono do anúncio. Só quem clicou é avisado (o outro ainda não tem o que ver)."""
    room, created = services.open_contact(user, anuncio_id)
    realtime.broadcast_room_changed(room.id, [user.pk])

    return room, created


def clear_context(user, room):
    services.clear_pending_anuncio(user, room)
    realtime.broadcast_room_changed(room.id, [user.pk])
