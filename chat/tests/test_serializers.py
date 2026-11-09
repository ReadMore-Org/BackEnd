from django.test import TestCase, override_settings
from unittest.mock import patch
from django.core.files.storage import FileSystemStorage

from chat.models.room import pair_key_for
from chat.serializers import ChatUserSerializer, display_name
from uploader.models import Image

from .helpers import make_user, make_anuncio


class PairKeyTests(TestCase):
    def test_order_does_not_matter(self):
        self.assertEqual(pair_key_for(3, 17), "3:17")
        self.assertEqual(pair_key_for(17, 3), "3:17")


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ChatUserTests(TestCase):
    def test_display_name_uses_profile_name(self):
        self.assertEqual(display_name(make_user("a@example.com", "  Ana Souza ")), "Ana Souza")

    def test_display_name_never_falls_back_to_the_email(self):
        for i, name in enumerate((None, "", "   ")):
            self.assertEqual(display_name(make_user(f"u{i}@example.com", name)), "Leitor")

    def test_avatar_prefers_uploaded_photo_then_google_picture(self):
        user = make_user("a@example.com", "Ana", google_picture="https://google.example/a.jpg")

        self.assertEqual(ChatUserSerializer(user).data["avatar"], "https://google.example/a.jpg")

        user.foto = Image.objects.create(file="images/foto.jpg", description="x")
        user.save()
        user.refresh_from_db()

        with patch.object(FileSystemStorage, "exists", return_value=True):
            self.assertTrue(ChatUserSerializer(user).data["avatar"].endswith("images/foto.jpg"))
        with patch.object(FileSystemStorage, "exists", return_value=False):
            self.assertEqual(ChatUserSerializer(user).data["avatar"], user.google_picture)

    def test_no_avatar(self):
        self.assertIsNone(ChatUserSerializer(make_user("a@example.com", "Ana")).data["avatar"])

    def test_payload_has_no_email(self):
        data = ChatUserSerializer(make_user("a@example.com", "Ana")).data

        self.assertEqual(set(data), {"id", "name", "avatar", "google_picture"})


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ChatCoverTests(TestCase):
    def setUp(self):
        self.user = make_user("cover@example.com", "Ana")
        self.anuncio = make_anuncio(self.user)
        self.book = self.anuncio.livro_usuario.livro
        self.book.google_book_id = "volume-real"
        self.book.isbn = "9788535914849"
        self.book.capa = Image.objects.create(file="images/missing.jpg")
        self.book.save()

    def test_card_keeps_cover_identifiers_when_local_file_is_missing(self):
        from chat.services import anuncio_card
        with patch.object(FileSystemStorage, "exists", return_value=False):
            card = anuncio_card(self.anuncio)
        self.assertIsNone(card["capa"])
        self.assertEqual(card["google_book_id"], "volume-real")
        self.assertEqual(card["isbn"], self.book.isbn)
        self.assertEqual(card["livro_id"], self.book.pk)
        self.assertEqual(card["id"], self.anuncio.pk)

    def test_legacy_snapshot_gets_cover_metadata_without_rewriting_history(self):
        from types import SimpleNamespace
        from chat.serializers.message import MessageSerializer
        snapshot = {"id": self.anuncio.pk, "titulo": "Título na época", "tipo": "troca", "capa": "/media/old.jpg"}
        message = SimpleNamespace(is_deleted=False, anuncio_card=snapshot)
        with patch.object(FileSystemStorage, "exists", return_value=False):
            card = MessageSerializer().get_anuncio(message)
        self.assertEqual(card["titulo"], "Título na época")
        self.assertEqual(card["google_book_id"], "volume-real")
        self.assertIsNone(card["capa"])
        self.assertEqual(snapshot["capa"], "/media/old.jpg")
        self.anuncio.delete()
        self.assertEqual(MessageSerializer().get_anuncio(message), snapshot)
