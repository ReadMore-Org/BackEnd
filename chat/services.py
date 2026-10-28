"""Camada de domínio do chat: conversas, participantes e mensagens.

Funções síncronas: as views as chamam direto e o consumer, via database_sync_to_async.
Toda função que age em nome de um usuário valida a participação dele na conversa aqui dentro,
então REST e WebSocket compartilham exatamente as mesmas regras de autorização.

Regra central do ReadMore: a única forma de uma conversa nascer é `open_contact`, chamada pelo
botão "Entrar em contato" de um anúncio do marketplace. Não existe criar conversa por busca de usuário.
"""

import logging
from datetime import UTC, datetime
from pathlib import PurePath

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import (
    Count,
    DateTimeField,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from core.models import Anuncio
from uploader.helpers.files import get_content_type

from .models import Membership, Message, Room
from .models.message import MESSAGE_MAX
from .models.room import pair_key_for

logger = logging.getLogger("chat")

PAGE_SIZE = 30
NEVER_READ = datetime(1970, 1, 1, tzinfo=UTC)  # 'sem leitura' nas subqueries

# Mesmo critério do marketplace (core/views/anuncio.py): só aparece enquanto o livro está lendo/lido.
VISIBLE_STATUSES = ("lendo", "lido")

NOT_A_MEMBER = "Você não participa desta conversa."
MESSAGE_NOT_FOUND = "Mensagem não encontrada."
ANUNCIO_UNAVAILABLE = "Este anúncio não está mais disponível."
CONTACT_SELF = "Você não pode iniciar uma conversa consigo mesmo."


# ---------------------------------------------------------------------------
# Participação e autorização
# ---------------------------------------------------------------------------


def get_membership(user, room):
    """Retorna a Membership do usuário ou levanta PermissionDenied se ele não participa da conversa."""
    if not (user and user.is_authenticated):
        raise PermissionDenied(NOT_A_MEMBER)

    try:
        return Membership.objects.get(user=user, room=room)
    except Membership.DoesNotExist as error:
        raise PermissionDenied(NOT_A_MEMBER) from error


def get_room_for(user, room_id):
    """Conversa pelo id, somente se o usuário participa dela (senão None, sem revelar se ela existe)."""
    if not (user and user.is_authenticated):
        return None

    return Room.objects.filter(pk=room_id, memberships__user=user).first()


def member_ids_for(room_id):
    """Ids dos participantes (lista vazia se a conversa não existe)."""
    if room_id is None:
        return []

    return list(
        Membership.objects.filter(room_id=room_id).values_list("user_id", flat=True)
    )


def member_ids(room):
    return member_ids_for(room.pk)


# ---------------------------------------------------------------------------
# Anúncio -> conversa
# ---------------------------------------------------------------------------


def anuncio_card(anuncio):
    """Retrato do anúncio mostrado no chat (JSON puro, guardado nas mensagens)."""
    livro_usuario = anuncio.livro_usuario
    livro = livro_usuario.livro
    capa = livro.capa

    return {
        "id": anuncio.pk,
        "tipo": anuncio.tipo,
        "titulo": livro.titulo,
        "capa": capa.url if capa is not None and capa.file else None,
        "dono": livro_usuario.usuario_id,
    }


def _anuncio_disponivel(anuncio_id):
    """Anúncio ainda visível no marketplace e de um dono ativo (senão None)."""
    return (
        Anuncio.objects.select_related(
            "livro_usuario__usuario", "livro_usuario__livro__capa"
        )
        .filter(
            pk=anuncio_id,
            livro_usuario__status__in=VISIBLE_STATUSES,
            livro_usuario__usuario__is_active=True,
        )
        .first()
    )


def open_contact(user, anuncio_id):
    """Abre (ou reabre) a conversa entre `user` e o dono do anúncio. Retorna (conversa, criada).

    É a única porta de entrada para criar uma conversa. A conversa é única por par de pessoas; o
    anúncio fica como cartão pendente para quem clicou e segue com a próxima mensagem dele.
    """
    if not (user and user.is_authenticated):
        raise PermissionDenied(NOT_A_MEMBER)

    anuncio = _anuncio_disponivel(anuncio_id)

    if anuncio is None:
        raise Anuncio.DoesNotExist(ANUNCIO_UNAVAILABLE)

    owner = anuncio.livro_usuario.usuario

    if owner.pk == user.pk:
        raise ValidationError(CONTACT_SELF)

    with transaction.atomic():
        room, created = Room.objects.get_or_create(
            pair_key=pair_key_for(user.pk, owner.pk)
        )

        for member in (user, owner):
            Membership.objects.get_or_create(room=room, user=member)

        Membership.objects.filter(room=room, user=user).update(pending_anuncio=anuncio)

    return room, created


def clear_pending_anuncio(user, room):
    """Descarta o cartão do anúncio que ainda não foi enviado."""
    get_membership(user, room)
    Membership.objects.filter(room=room, user=user).update(pending_anuncio=None)


# ---------------------------------------------------------------------------
# Conversas
# ---------------------------------------------------------------------------


def delete_room_files(room):
    """Apaga do storage os arquivos das mensagens da conversa."""
    for message in room.messages.exclude(file="").exclude(file__isnull=True):
        _remove_file(message)


def _remove_file(message):
    """Apaga o arquivo do storage sem derrubar a operação principal se o storage falhar."""
    try:
        message.file.delete(save=False)
    except Exception:  # noqa: BLE001 - falha de storage não pode impedir a exclusão lógica
        logger.exception("Falha ao remover o arquivo da mensagem %s", message.pk)


def rooms_for(user, only=None):
    """Conversas do usuário, da mais recente para a mais antiga, anotadas com
    .unread, .last_message, .other (o outro participante) e .pending_anuncio_obj
    (número de queries constante).

    Uma conversa só aparece na lista de quem tem mensagens nela ou um cartão de anúncio pendente: assim
    o dono do anúncio só vê a conversa quando recebe a primeira mensagem. `only` restringe a uma
    conversa específica (usado por room_summary) e ignora essa regra.
    """
    mine = Membership.objects.filter(room=OuterRef("pk"), user=user)
    last_read = mine.values("last_read_at")[:1]
    unread = (
        Message.objects.filter(
            room=OuterRef("pk"), is_deleted=False, created__gt=OuterRef("my_last_read")
        )
        .exclude(author=user)
        .order_by()
        .values("room")
        .annotate(total=Count("pk"))
        .values("total")
    )
    last_id = (
        Message.objects.filter(room=OuterRef("pk"))
        .order_by("-created", "-id")
        .values("id")[:1]
    )

    if only is not None:
        base = Room.objects.filter(pk=only.pk, memberships__user=user)
    else:
        base = Room.objects.filter(
            Q(memberships__user=user)
            & (
                Q(last_message_at__isnull=False)
                | Q(memberships__pending_anuncio__isnull=False)
            )
        )

    rooms = list(
        base.annotate(
            my_last_read=Coalesce(
                Subquery(last_read),
                Value(NEVER_READ, output_field=DateTimeField()),
                output_field=DateTimeField(),
            ),
            unread=Coalesce(Subquery(unread, output_field=IntegerField()), 0),
            last_message_id=Subquery(last_id),
        ).order_by(F("last_message_at").desc(nulls_last=True), "-id")
    )

    room_ids = [room.pk for room in rooms]
    others = {
        membership.room_id: membership.user
        for membership in Membership.objects.filter(room_id__in=room_ids)
        .exclude(user=user)
        .select_related("user__foto", "user__chat_presence")
    }
    pending = {
        membership.room_id: membership.pending_anuncio
        for membership in Membership.objects.filter(
            room_id__in=room_ids, user=user, pending_anuncio__isnull=False
        ).select_related(
            "pending_anuncio__livro_usuario__livro__capa",
        )
    }
    last_ids = [room.last_message_id for room in rooms if room.last_message_id]
    messages = Message.objects.select_related(
        "author__foto", "reply_to__author"
    ).in_bulk(last_ids)

    for room in rooms:
        room.other = others.get(room.pk)
        room.pending_anuncio_obj = pending.get(room.pk)
        room.last_message = messages.get(room.last_message_id)

    return rooms


def room_summary(user, room):
    """O mesmo que rooms_for, para uma única conversa (mesmas anotações)."""
    rooms = rooms_for(user, only=room)

    if not rooms:
        raise PermissionDenied(NOT_A_MEMBER)

    return rooms[0]


# ---------------------------------------------------------------------------
# Mensagens
# ---------------------------------------------------------------------------


def _clean_body(body):
    """Valida e normaliza o texto da mensagem (1 a MESSAGE_MAX caracteres)."""
    if body is not None and not isinstance(body, str):
        raise ValidationError("Mensagem inválida.")

    body = (body or "").strip()

    if not body or len(body) > MESSAGE_MAX:
        raise ValidationError(f"A mensagem deve ter de 1 a {MESSAGE_MAX} caracteres.")

    return body


def _resolve_reply(room, reply_to_id):
    if reply_to_id is None:
        return None

    reply_to = Message.objects.filter(pk=reply_to_id, room=room).first()

    if reply_to is None:
        raise ValidationError("A mensagem respondida não pertence a esta conversa.")

    return reply_to


def send_message(user, room, body=None, file=None, reply_to_id=None):
    """Envia texto ou arquivo (exatamente um dos dois) para uma conversa da qual o usuário participa.

    Se o usuário abriu a conversa por um anúncio e ainda não enviou o cartão, ele vai junto.
    """
    membership = get_membership(user, room)

    if (body is None) == (file is None):
        raise ValidationError("Envie texto ou arquivo, não ambos nem nenhum.")

    extra = {}

    if file is not None:
        limit = settings.CHAT_MAX_UPLOAD_MB * 1024 * 1024

        if not file.size:
            raise ValidationError("O arquivo está vazio.")

        if file.size > limit:
            raise ValidationError(f"O arquivo excede {settings.CHAT_MAX_UPLOAD_MB} MB.")

        extra = {
            "file_name": PurePath(file.name or "arquivo").name[:255] or "arquivo",
            "file_size": file.size,
            # Tipo real pelo conteúdo (libmagic), o mesmo mecanismo do uploader da plataforma.
            "file_content_type": get_content_type(file),
        }
    else:
        body = _clean_body(body)

    reply_to = _resolve_reply(room, reply_to_id)
    card = None

    if membership.pending_anuncio_id:
        anuncio = _anuncio_disponivel(membership.pending_anuncio_id)
        card = anuncio_card(anuncio) if anuncio is not None else None

    with transaction.atomic():
        message = Message.objects.create(
            room=room,
            author=user,
            body=body,
            file=file,
            reply_to=reply_to,
            anuncio_card=card,
            **extra,
        )
        Room.objects.filter(pk=room.pk).update(last_message_at=message.created)
        room.last_message_at = message.created
        Membership.objects.filter(user=user, room=room).update(
            last_read_at=message.created, pending_anuncio=None
        )

    return message


def _own_message(user, room, message_id):
    """Mensagem da conversa escrita pelo usuário (que ainda precisa participar dela)."""
    get_membership(user, room)
    message = Message.objects.filter(pk=message_id, room=room).first()

    if message is None:
        raise Message.DoesNotExist(MESSAGE_NOT_FOUND)

    if message.author_id != user.pk:
        raise PermissionDenied("Apenas o autor pode alterar a mensagem.")

    return message


def edit_message(user, room, message_id, body):
    """Edita o texto de uma mensagem própria (não apagada e sem arquivo)."""
    message = _own_message(user, room, message_id)

    if message.is_deleted:
        raise ValidationError("Mensagem apagada não pode ser editada.")

    if message.file:
        raise ValidationError("Só mensagens de texto podem ser editadas.")

    message.body = _clean_body(body)
    message.edited_at = timezone.now()
    message.save(update_fields=["body", "edited_at"])

    return message


def delete_message(user, room, message_id):
    """Apaga (exclusão lógica) uma mensagem própria e remove o arquivo do storage."""
    message = _own_message(user, room, message_id)

    if message.is_deleted:
        return message

    if message.file:
        _remove_file(message)

    message.file = None
    message.file_name = ""
    message.file_size = None
    message.file_content_type = ""
    message.body = None
    message.anuncio_card = None
    message.is_deleted = True
    message.save(
        update_fields=[
            "file",
            "file_name",
            "file_size",
            "file_content_type",
            "body",
            "anuncio_card",
            "is_deleted",
        ]
    )

    return message


def get_message_for(user, message_id):
    """Mensagem pelo id somente se o usuário participa da conversa dela (senão None)."""
    if not (user and user.is_authenticated):
        return None

    return (
        Message.objects.filter(pk=message_id, room__memberships__user=user)
        .select_related("room")
        .first()
    )


def read_by_all_ids(room, messages):
    """Ids das mensagens já lidas por todos os demais participantes da conversa (1 query)."""
    reads = list(
        Membership.objects.filter(room=room).values_list("user_id", "last_read_at")
    )
    result = set()

    for message in messages:
        others = [read for user_id, read in reads if user_id != message.author_id]

        if others and all(read is not None and read >= message.created for read in others):
            result.add(message.id)

    return result


def mark_read(user, room):
    """Marca a conversa como lida; retorna os ids das mensagens de outros autores que
    passaram a estar lidas por todos."""
    membership = get_membership(user, room)
    previous = membership.last_read_at
    membership.last_read_at = timezone.now()
    membership.save(update_fields=["last_read_at"])

    queryset = Message.objects.filter(room=room, is_deleted=False).exclude(author=user)

    if previous:
        queryset = queryset.filter(created__gt=previous)

    candidates = list(queryset.filter(created__lte=membership.last_read_at))
    done = read_by_all_ids(room, candidates)

    return [message.id for message in candidates if message.id in done]


def message_page(room, before_id=None, size=PAGE_SIZE):
    """Até `size` mensagens mais recentes (anteriores a before_id), em ordem cronológica,
    e se existem mensagens ainda mais antigas."""
    queryset = Message.objects.filter(room=room)

    if before_id is not None:
        queryset = queryset.filter(pk__lt=before_id)

    page = list(
        queryset.select_related("author__foto", "reply_to__author").order_by("-id")[
            : size + 1
        ],
    )
    has_more = len(page) > size
    page = page[:size]
    page.reverse()

    return page, has_more
