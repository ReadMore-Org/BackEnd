from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat import actions, services
from chat.models import Room
from chat.serializers import (
    ContactSerializer,
    MessageCreateSerializer,
    MessageSerializer,
    RoomSerializer,
)

from ._common import domain_errors


class RoomViewSet(viewsets.GenericViewSet):
    """Conversas do usuário autenticado (sempre entre duas pessoas).

    A única forma de criar uma conversa é `POST rooms/contact/` a partir de um anúncio do marketplace;
    não existe criar, renomear, sair nem adicionar participantes.

    A autorização é por PARTICIPAÇÃO na conversa. Uma conversa da qual o usuário não participa
    responde 404, igual a uma conversa inexistente.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RoomSerializer
    queryset = Room.objects.none()
    lookup_value_regex = r"\d+"

    # ---- helpers ----

    def _room(self, pk):
        room = services.get_room_for(self.request.user, pk)

        if room is None:
            raise NotFound("Conversa não encontrada.")

        return room

    def _detail(self, room, http_status=status.HTTP_200_OK):
        summary = services.room_summary(self.request.user, room)

        return Response(
            RoomSerializer(summary, context=self.get_serializer_context()).data,
            status=http_status,
        )

    # ---- conversas ----

    @extend_schema(summary="Conversas do usuário", responses={200: RoomSerializer(many=True)})
    def list(self, request):
        page = self.paginate_queryset(services.rooms_for(request.user))
        serializer = RoomSerializer(
            page, many=True, context=self.get_serializer_context()
        )

        return self.get_paginated_response(serializer.data)

    @extend_schema(summary="Detalhes da conversa", responses={200: RoomSerializer})
    def retrieve(self, request, pk=None):
        return self._detail(self._room(pk))

    @extend_schema(
        summary="Iniciar (ou reabrir) a conversa com o dono de um anúncio",
        request=ContactSerializer,
        responses={200: RoomSerializer, 201: RoomSerializer},
    )
    @action(detail=False, methods=["post"], url_path="contact")
    def contact(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with domain_errors():
            room, created = actions.open_contact(
                request.user, serializer.validated_data["anuncio"]
            )

        return self._detail(
            room, status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    @extend_schema(
        summary="Descartar o cartão do anúncio ainda não enviado",
        request=None,
        responses={204: None},
    )
    @action(detail=True, methods=["delete"], url_path="context")
    def clear_context(self, request, pk=None):
        room = self._room(pk)

        with domain_errors():
            actions.clear_context(request.user, room)

        return Response(status=status.HTTP_204_NO_CONTENT)

    # ---- mensagens ----

    @extend_schema(
        summary="Histórico (GET) ou envio (POST) de mensagens",
        request=MessageCreateSerializer,
        responses={200: MessageSerializer(many=True), 201: MessageSerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="messages")
    def messages(self, request, pk=None):
        room = self._room(pk)

        if request.method == "POST":
            return self._create_message(request, room)

        before = request.query_params.get("before")

        if before not in (None, ""):
            try:
                before = int(before)
            except ValueError as error:
                raise ValidationError({"before": "Informe um id numérico."}) from error
        else:
            before = None

        page, has_more = services.message_page(room, before)
        read_ids = services.read_by_all_ids(room, page)
        data = MessageSerializer(page, many=True, context={"read_ids": read_ids}).data

        return Response(
            {
                "results": data,
                "has_more": has_more,
                # Mensagens vêm em ordem cronológica: a mais antiga da página é o cursor da próxima.
                "next_before": page[0].id if has_more and page else None,
            }
        )

    def _create_message(self, request, room):
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with domain_errors():
            message = actions.send_message(
                request.user,
                room,
                body=data["body"],
                file=data["file"],
                reply_to_id=data.get("reply_to"),
            )

        read_ids = services.read_by_all_ids(room, [message])

        return Response(
            MessageSerializer(message, context={"read_ids": read_ids}).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(summary="Marcar conversa como lida", request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        room = self._room(pk)

        with domain_errors():
            actions.mark_read(request.user, room)

        return Response(status=status.HTTP_204_NO_CONTENT)
