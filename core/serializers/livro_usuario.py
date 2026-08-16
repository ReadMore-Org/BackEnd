from rest_framework.serializers import ModelSerializer

from core.models import LivroUsuario
from .livro import LivroRetrieveSerializer


class LivroUsuarioSerializer(ModelSerializer):
    livro = LivroRetrieveSerializer(read_only=True)

    class Meta:
        model = LivroUsuario
        fields = "__all__"
        read_only_fields = ("usuario",)

class LivroUsuarioWriteSerializer(ModelSerializer):
    class Meta:
        model = LivroUsuario
        fields = ("livro", "status")