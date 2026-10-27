from rest_framework import serializers

from uploader.helpers.files import CONTENT_TYPE_JPG, CONTENT_TYPE_PNG
from uploader.models import Image
from uploader.helpers.images import image_url


class ImageUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ["attachment_key", "file", "description", "uploaded_on", "url"]
        read_only_fields = ["attachment_key", "uploaded_on", "url"]
        extra_kwargs = {"file": {"write_only": True}}

    def validate_file(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("A imagem deve ter até 5 MB.")
        valid_content_types = [CONTENT_TYPE_JPG, CONTENT_TYPE_PNG]
        if value.content_type not in valid_content_types:
            raise serializers.ValidationError("Invalid or corrupted image.")
        return value


class ImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Image
        fields = ["url", "description", "uploaded_on"]
        read_only_fields = ["url", "attachment_key", "uploaded_on"]

    def get_url(self, obj):
        return image_url(obj, self.context.get("request"))

    def create(self, validated_data):
        raise NotImplementedError("Use ImageUploadSerializer to create images.")
