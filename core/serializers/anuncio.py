from rest_framework.serializers import (
    ModelSerializer,
    SerializerMethodField,
    ValidationError,
)
 
from core.models import Anuncio, User
from core.serializers.livro import LivroRetrieveSerializer
 
 
class DonoAnuncioSerializer(ModelSerializer):
    """Dados públicos do dono nas listagens (sem email)."""
 
    foto_url = SerializerMethodField()
 
    class Meta:
        model = User
        fields = ["id", "name", "foto_url"]
 
    def get_foto_url(self, obj):
        if obj.foto and obj.foto.file:
            request = self.context.get("request")
            url = obj.foto.file.url
            return request.build_absolute_uri(url) if request else url
        return obj.google_picture
 
 
class DonoAnuncioDetalheSerializer(DonoAnuncioSerializer):
    """Dados do dono na página de detalhe (inclui email e bio)."""
 
    class Meta(DonoAnuncioSerializer.Meta):
        fields = ["id", "name", "email", "bio", "foto_url"]
 
 
class AnuncioListSerializer(ModelSerializer):
    livro = LivroRetrieveSerializer(source="livro_usuario.livro", read_only=True)
    dono = DonoAnuncioSerializer(source="livro_usuario.usuario", read_only=True)
 
    class Meta:
        model = Anuncio
        fields = [
            "id",
            "tipo",
            "condicao",
            "observacao",
            "criado_em",
            "livro",
            "dono",
        ]
 
 
class AnuncioDetailSerializer(AnuncioListSerializer):
    dono = DonoAnuncioDetalheSerializer(
        source="livro_usuario.usuario", read_only=True
    )
 
 
class AnuncioWriteSerializer(ModelSerializer):
    class Meta:
        model = Anuncio
        fields = ["livro_usuario", "tipo", "condicao", "observacao"]
 
    def validate_livro_usuario(self, value):
        request = self.context["request"]
 
        if value.usuario_id != request.user.id:
            raise ValidationError("Este livro não está na sua estante.")
 
        if value.status not in ("lendo", "lido"):
            raise ValidationError(
                "Só é possível anunciar livros com status 'Lendo' ou 'Lido'."
            )
 
        if self.instance is not None and value != self.instance.livro_usuario:
            raise ValidationError("Não é possível trocar o livro de um anúncio.")
 
        return value