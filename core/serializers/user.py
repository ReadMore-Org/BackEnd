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
            "meta_leitura"
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
        ]

        read_only_fields = ["id", "email"]
