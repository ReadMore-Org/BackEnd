from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from chat import actions, services
from chat.consumers import CLOSE_UNAUTHORIZED
from chat.models import Message, UserPresence
from config.asgi import application

from .helpers import make_anuncio, make_user, token_for

TIMEOUT = 2


async def open_socket(user=None, token=None):
    token = token if token is not None else (token_for(user) if user else "")
    path = f"/ws/chat/?token={token}" if token else "/ws/chat/"
    communicator = WebsocketCommunicator(application, path)
    connected, _ = await communicator.connect()

    assert connected

    return communicator


async def next_event(communicator, expected_type):
    event = await communicator.receive_json_from(timeout=TIMEOUT)

    assert event["type"] == expected_type, f"esperava {expected_type!r}, veio {event!r}"

    return event


class ConsumerTests(TransactionTestCase):
    def setUp(self):
        self.ana = make_user("ana@example.com", "Ana")
        self.bia = make_user("bia@example.com", "Bia")
        self.anuncio = make_anuncio(self.bia, titulo="Dom Casmurro")
        self.room, _ = services.open_contact(self.ana, self.anuncio.pk)

    async def connect_both(self):
        ana = await open_socket(self.ana)
        bia = await open_socket(self.bia)
        presence = await next_event(ana, "presence")  # a Bia ficou online

        assert presence["user_id"] == self.bia.pk and presence["online"] is True

        return ana, bia

    # ---- autenticação ----

    async def test_anonymous_connection_is_closed_with_4401(self):
        for communicator in (
            WebsocketCommunicator(application, "/ws/chat/"),
            WebsocketCommunicator(application, "/ws/chat/?token=lixo"),
        ):
            connected, _ = await communicator.connect()
            output = await communicator.receive_output(timeout=TIMEOUT)

            self.assertTrue(connected)
            self.assertEqual(output["type"], "websocket.close")
            self.assertEqual(output["code"], CLOSE_UNAUTHORIZED)

    async def test_inactive_user_cannot_connect(self):
        token = token_for(self.ana)
        self.ana.is_active = False
        await database_sync_to_async(self.ana.save)()

        communicator = WebsocketCommunicator(application, f"/ws/chat/?token={token}")
        await communicator.connect()
        output = await communicator.receive_output(timeout=TIMEOUT)

        self.assertEqual(output["code"], CLOSE_UNAUTHORIZED)

    # ---- mensagens ----

    async def test_text_message_reaches_both_participants(self):
        ana, bia = await self.connect_both()

        await ana.send_json_to({"action": "send", "room": self.room.pk, "body": "Oi, Bia!"})

        for communicator in (ana, bia):
            new = await next_event(communicator, "message.new")
            updated = await next_event(communicator, "room.updated")

            self.assertEqual(new["room"], self.room.pk)
            self.assertEqual(new["message"]["body"], "Oi, Bia!")
            self.assertEqual(new["message"]["author"]["name"], "Ana")
            self.assertEqual(new["message"]["anuncio"]["titulo"], "Dom Casmurro")
            self.assertEqual(updated["summary"]["last_message"]["id"], new["message"]["id"])

        self.assertEqual(updated["summary"]["unread"], 1)  # visto pela Bia
        self.assertEqual(updated["summary"]["name"], "Ana")

        await ana.disconnect()
        await bia.disconnect()

    async def test_author_comes_from_the_token_never_from_the_client(self):
        ana, bia = await self.connect_both()

        await ana.send_json_to(
            {"action": "send", "room": self.room.pk, "body": "oi", "author": self.bia.pk, "user": self.bia.pk}
        )
        event = await next_event(bia, "message.new")

        self.assertEqual(event["message"]["author"]["id"], self.ana.pk)

        await ana.disconnect()
        await bia.disconnect()

    async def test_typing_is_sent_only_to_the_other_person(self):
        ana, bia = await self.connect_both()

        await ana.send_json_to({"action": "typing", "room": self.room.pk})
        event = await next_event(bia, "typing")

        self.assertEqual(event["user"]["id"], self.ana.pk)
        self.assertTrue(await ana.receive_nothing(timeout=0.3))

        await ana.disconnect()
        await bia.disconnect()

    async def test_read_sends_receipt_and_zeroes_the_counter(self):
        ana, bia = await self.connect_both()
        message = await database_sync_to_async(actions.send_message)(self.ana, self.room, body="leia")
        await next_event(ana, "message.new")
        await next_event(ana, "room.updated")
        await next_event(bia, "message.new")
        await next_event(bia, "room.updated")

        await bia.send_json_to({"action": "read", "room": self.room.pk})

        receipt = await next_event(ana, "read.receipt")
        mine = await next_event(bia, "read.receipt")
        updated = await next_event(bia, "room.updated")

        self.assertEqual(receipt["message_ids"], [message.pk])
        self.assertEqual(mine["message_ids"], [message.pk])
        self.assertEqual(updated["summary"]["unread"], 0)

        await ana.disconnect()
        await bia.disconnect()

    async def test_edit_and_delete(self):
        ana, bia = await self.connect_both()
        message = await database_sync_to_async(actions.send_message)(self.ana, self.room, body="errado")

        for communicator in (ana, bia):
            await next_event(communicator, "message.new")
            await next_event(communicator, "room.updated")

        await ana.send_json_to({"action": "edit", "room": self.room.pk, "message_id": message.pk, "body": "certo"})
        update = await next_event(bia, "message.update")

        self.assertEqual(update["message"]["body"], "certo")
        self.assertIsNotNone(update["message"]["edited_at"])
        await next_event(bia, "room.updated")

        await ana.send_json_to({"action": "delete", "room": self.room.pk, "message_id": message.pk})
        await next_event(ana, "message.update")
        await next_event(ana, "room.updated")
        await next_event(ana, "message.update")
        await next_event(ana, "room.updated")
        deleted = await next_event(bia, "message.update")

        self.assertTrue(deleted["message"]["is_deleted"])
        self.assertIsNone(deleted["message"]["body"])

        await ana.disconnect()
        await bia.disconnect()

    async def test_only_the_author_can_edit_or_delete(self):
        ana, bia = await self.connect_both()
        message = await database_sync_to_async(actions.send_message)(self.ana, self.room, body="minha")

        for communicator in (ana, bia):
            await next_event(communicator, "message.new")
            await next_event(communicator, "room.updated")

        await bia.send_json_to({"action": "delete", "room": self.room.pk, "message_id": message.pk})
        error = await next_event(bia, "error")

        self.assertEqual(error["action"], "delete")
        self.assertEqual(error["detail"], "Apenas o autor pode alterar a mensagem.")

        await bia.send_json_to({"action": "edit", "room": self.room.pk, "message_id": message.pk, "body": "x"})
        await next_event(bia, "error")

        stored = await database_sync_to_async(Message.objects.get)(pk=message.pk)

        self.assertEqual(stored.body, "minha")
        self.assertFalse(stored.is_deleted)

        await ana.disconnect()
        await bia.disconnect()

    # ---- autorização e entradas inválidas ----

    async def test_stranger_cannot_use_the_room(self):
        carla = await database_sync_to_async(make_user)("carla@example.com", "Carla")
        stranger = await open_socket(carla)

        for payload in (
            {"action": "send", "room": self.room.pk, "body": "intruso"},
            {"action": "typing", "room": self.room.pk},
            {"action": "read", "room": self.room.pk},
        ):
            await stranger.send_json_to(payload)
            error = await next_event(stranger, "error")

            self.assertEqual(error["detail"], "Conversa não encontrada.")

        self.assertEqual(await database_sync_to_async(Message.objects.count)(), 0)

        await stranger.disconnect()

    async def test_invalid_frames_do_not_drop_the_connection(self):
        ana = await open_socket(self.ana)

        await ana.send_to(text_data="isto não é json")
        await next_event(ana, "error")

        await ana.send_json_to(["lista"])
        await next_event(ana, "error")

        await ana.send_json_to({"action": "explodir", "room": self.room.pk})
        self.assertEqual((await next_event(ana, "error"))["detail"], "Ação desconhecida.")

        await ana.send_json_to({"action": "send", "room": "abc", "body": "oi"})
        await next_event(ana, "error")

        await ana.send_json_to({"action": "send", "room": self.room.pk, "body": 123})
        await next_event(ana, "error")

        await ana.send_to(text_data="x" * (16 * 1024 + 1))
        await next_event(ana, "error")

        await ana.send_json_to({"action": "send", "room": self.room.pk, "body": "ainda funciona"})
        await next_event(ana, "message.new")

        await ana.disconnect()

    # ---- presença ----

    async def test_presence_is_broadcast_to_the_other_person(self):
        ana, bia = await self.connect_both()

        await bia.disconnect()
        offline = await next_event(ana, "presence")

        self.assertEqual(offline["user_id"], self.bia.pk)
        self.assertFalse(offline["online"])
        self.assertIsNotNone(offline["last_seen"])

        await ana.disconnect()

    async def test_two_tabs_keep_the_user_online_until_the_last_one_closes(self):
        ana = await open_socket(self.ana)
        first_tab = await open_socket(self.bia)
        await next_event(ana, "presence")
        second_tab = await open_socket(self.bia)

        self.assertTrue(await ana.receive_nothing(timeout=0.3))  # a 2ª aba não muda nada

        await first_tab.disconnect()
        self.assertTrue(await ana.receive_nothing(timeout=0.3))

        presence = await database_sync_to_async(UserPresence.objects.get)(user=self.bia)

        self.assertEqual(presence.connections, 1)

        await second_tab.disconnect()
        offline = await next_event(ana, "presence")

        self.assertFalse(offline["online"])

        await ana.disconnect()

    # ---- contato em tempo real ----

    async def test_contact_updates_only_the_initiator_tabs(self):
        carla = await database_sync_to_async(make_user)("carla@example.com", "Carla")
        outro = await database_sync_to_async(make_anuncio)(carla, "Livro da Carla")
        ana, bia = await self.connect_both()

        await database_sync_to_async(actions.open_contact)(self.ana, outro.pk)
        event = await next_event(ana, "room.updated")

        self.assertEqual(event["summary"]["name"], "Carla")
        self.assertEqual(event["summary"]["pending_anuncio"]["titulo"], "Livro da Carla")
        self.assertTrue(await bia.receive_nothing(timeout=0.3))

        await ana.disconnect()
        await bia.disconnect()
