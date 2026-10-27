import base64
import tempfile
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings, RequestFactory
from core.models import User
from core.serializers.anuncio import DonoAnuncioDetalheSerializer
from uploader.models import Image
from uploader.serializers.image import ImageSerializer
from uploader.helpers.images import image_url


class ImageURLTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(
            MEDIA_ROOT=self.directory.name,
            MEDIA_URL='/media/',
            STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}},
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.request = RequestFactory().get('/', HTTP_HOST='localhost:8000')

    def test_existing_image_has_absolute_url(self):
        image = Image.objects.create(file='images/photo.png')
        image.file.save('photo.png', ContentFile(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')), save=True)
        url = ImageSerializer(image, context={'request': self.request}).data['url']
        self.assertEqual(url, f'http://localhost:8000/media/{image.file.name}')

    def test_missing_file_returns_null_instead_of_broken_url(self):
        image = Image.objects.create(file='images/missing.png')
        self.assertIsNone(ImageSerializer(image, context={'request': self.request}).data['url'])

    def test_empty_file_does_not_raise(self):
        self.assertIsNone(image_url(Image(), self.request))
        self.assertIsNone(image_url(None, self.request))

    def test_marketplace_avatar_falls_back_to_google(self):
        image = Image.objects.create(file='images/missing-avatar.png')
        user = User.objects.create_user('avatar@example.com', 'password123', foto=image, google_picture='https://lh3.googleusercontent.com/photo')
        data = DonoAnuncioDetalheSerializer(user, context={'request': self.request}).data
        self.assertEqual(data['foto_url'], user.google_picture)

    def test_remote_storage_does_not_require_local_file(self):
        from unittest.mock import Mock
        image = Mock()
        image.file.url = 'https://res.cloudinary.com/demo/image/upload/photo.jpg'
        self.assertEqual(image_url(image, self.request), image.file.url)
        image.file.storage.exists.assert_not_called()

    def test_missing_local_file_can_use_configured_remote_fallback(self):
        from unittest.mock import Mock, patch
        image = Image.objects.create(file='images/remote.png')
        remote = Mock()
        remote.url.return_value = 'https://res.cloudinary.com/demo/image/upload/media/images/remote.png'
        with override_settings(STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
            'media_fallback': {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'},
        }), patch('uploader.helpers.images.storages', {'media_fallback': remote}):
            self.assertEqual(image_url(image, self.request), remote.url.return_value)
            remote.url.assert_called_once_with(image.file.name)
            remote.exists.assert_not_called()

    def test_upload_rejects_cover_over_five_megabytes(self):
        from unittest.mock import Mock
        from rest_framework.exceptions import ValidationError
        from uploader.serializers.image import ImageUploadSerializer
        with self.assertRaises(ValidationError):
            ImageUploadSerializer().validate_file(Mock(size=5 * 1024 * 1024 + 1, content_type='image/png'))
