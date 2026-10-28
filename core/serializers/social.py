from rest_framework import serializers
from core.models import InteracaoLivro
from core.serializers.livro import LivroRetrieveSerializer


class NotaSerializer(serializers.Serializer):
    nota = serializers.IntegerField(min_value=1, max_value=5)


class InteracaoLivroSerializer(serializers.ModelSerializer):
    nota = serializers.IntegerField(min_value=1, max_value=5, allow_null=True, required=False)
    favorito = serializers.BooleanField(required=False)

    class Meta:
        model = InteracaoLivro
        fields = ["nota", "favorito"]


class FavoritoSerializer(serializers.ModelSerializer):
    livro = LivroRetrieveSerializer(read_only=True)

    class Meta:
        model = InteracaoLivro
        fields = ["id", "livro", "favorito", "nota"]


class ImportarInteracaoSerializer(serializers.Serializer):
    google_book_id = serializers.CharField(max_length=100, required=False, allow_null=True)
    titulo = serializers.CharField(max_length=260)
    isbn = serializers.CharField(max_length=13, required=False, allow_null=True)

    def validate(self, attrs):
        if not attrs.get("google_book_id") and not attrs.get("isbn"):
            raise serializers.ValidationError("Informe o identificador do catálogo ou o ISBN da edição.")
        return attrs
