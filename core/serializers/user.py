from rest_framework import serializers
from rest_framework.serializers import ModelSerializer, SlugRelatedField
from uploader.serializers import ImageSerializer

from core.models.user import User

from uploader.models import Image


class UserSerializer(ModelSerializer):
    class Meta:
        model = User

        fields = [
            "id",
            "email",
            "name",
            "bio",
            "meta_leitura",
            "foto",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "groups",
            "google_picture",
            "show_onboarding",
        ]

        depth = 1


class UserRegistrationSerializer(ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User

        fields = ["id", "email", "name", "password"]

    def create(self, validated_data):

        return User.objects.create_user(**validated_data)


class MeSerializer(ModelSerializer):
    foto_attachment_key = SlugRelatedField(
        source="foto",
        queryset=Image.objects.all(),
        slug_field="attachment_key",
        required=False,
        write_only=True,
    )

    foto = ImageSerializer(read_only=True)

    class Meta:
        model = User

        fields = [
            "id",
            "email",
            "name",
            "bio",
            "meta_leitura",
            "foto",
            "foto_attachment_key",
            "google_picture",
            "show_onboarding",
            "reading_preferences",
            "reading_preferences_status",
        ]

        read_only_fields = ["id", "email", "reading_preferences", "reading_preferences_status"]


class PreferredBookSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=200, required=False, allow_blank=True)
    title = serializers.CharField(max_length=260)
    authors = serializers.ListField(child=serializers.CharField(max_length=150), max_length=10)
    source = serializers.ChoiceField(choices=['local', 'google', 'openlibrary'], default='google')
    isbn = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)


class ReadingPreferencesSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['completed', 'skipped'])
    categories = serializers.ListField(child=serializers.CharField(max_length=80), max_length=100, default=list)
    authors = serializers.ListField(child=serializers.CharField(max_length=150), max_length=100, default=list)
    books = PreferredBookSerializer(many=True, max_length=100, default=list)

    def validate(self, data):
        for key in ('categories', 'authors'):
            data[key] = list(dict.fromkeys(data[key]))
        if data['status'] == 'skipped':
            data.update(categories=[], authors=[], books=[])
        return data
