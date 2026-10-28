from django.test import TestCase

from chat.models.room import pair_key_for
from chat.serializers import ChatUserSerializer, display_name
from uploader.models import Image

from .helpers import make_user


class PairKeyTests(TestCase):
    def test_order_does_not_matter(self):
        self.assertEqual(pair_key_for(3, 17), "3:17")
        self.assertEqual(pair_key_for(17, 3), "3:17")


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

        self.assertTrue(ChatUserSerializer(user).data["avatar"].endswith("images/foto.jpg"))

    def test_no_avatar(self):
        self.assertIsNone(ChatUserSerializer(make_user("a@example.com", "Ana")).data["avatar"])

    def test_payload_has_no_email(self):
        data = ChatUserSerializer(make_user("a@example.com", "Ana")).data

        self.assertEqual(set(data), {"id", "name", "avatar"})
