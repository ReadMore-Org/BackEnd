from rest_framework import serializers
from rest_framework.serializers import (
    ModelSerializer,
    SlugRelatedField,
    ListField,
    CharField,
    PrimaryKeyRelatedField,
    StringRelatedField,
)

from uploader.models import Image
from uploader.serializers import ImageSerializer

from core.serializers.autor import AutorSerializer
from core.models import Livro, Autor, Categoria


class ResumoAvaliacoesMixin:
    def to_representation(self, instance):
        data = super().to_representation(instance)
        from django.db.models import Avg, Count
        resumo = instance.interacoes.filter(nota__isnull=False).aggregate(media=Avg("nota"), total=Count("id"))
        data["nota"] = round(resumo["media"], 1) if resumo["total"] else None
        data["avaliacoes"] = resumo["total"]
        return data


class LivroRetrieveSerializer(ResumoAvaliacoesMixin, ModelSerializer):
    categorias = StringRelatedField(source="categoria", many=True, read_only=True)
    capa = ImageSerializer(required=False)

    class Meta:
        model = Livro
        fields = "__all__"
        depth = 1


class LivroSerializer(ResumoAvaliacoesMixin, ModelSerializer):
    categorias = StringRelatedField(source="categoria", many=True, read_only=True)
    autores = AutorSerializer(many=True, read_only=True)
    autores_nomes = ListField(
        child=CharField(max_length=50),
        write_only=True,
        required=False,
    )
    categoria = PrimaryKeyRelatedField(
        many=True,
        queryset=Categoria.objects.all(),
        required=False,
    )
    capa_attachment_key = SlugRelatedField(
        source="capa",
        queryset=Image.objects.all(),
        slug_field="attachment_key",
        required=False,
        write_only=True,
    )
    capa = ImageSerializer(required=False, read_only=True)

    class Meta:
        model = Livro
        fields = "__all__"

    def create(self, validated_data):
        autores_nomes = validated_data.pop("autores_nomes", [])
        categoria = validated_data.pop("categoria", [])

        livro = Livro.objects.create(**validated_data)

        if categoria:
            livro.categoria.set(categoria)

        self._set_autores(livro, autores_nomes)
        return livro

    def update(self, instance, validated_data):
        autores_nomes = validated_data.pop("autores_nomes", None)
        categoria = validated_data.pop("categoria", None)

        livro = super().update(instance, validated_data)

        if categoria is not None:
            livro.categoria.set(categoria)

        if autores_nomes is not None:
            self._set_autores(livro, autores_nomes)

        return livro

    def _set_autores(self, livro, autores_nomes):
        if not autores_nomes:
            return
        autores = []
        for nome in autores_nomes:
            nome = nome.strip()
            if not nome:
                continue
            autor, _ = Autor.objects.get_or_create(nome=nome)
            autores.append(autor)
        livro.autores.set(autores)


class CadastroManualSerializer(LivroSerializer):
    titulo = serializers.CharField(max_length=260)
    autores_nomes = ListField(child=CharField(max_length=50), allow_empty=False, write_only=True)
    paginas = serializers.IntegerField(min_value=1, max_value=2147483647, required=False, allow_null=True)
    status = serializers.ChoiceField(choices=["quero_ler", "lendo", "lido"], default="quero_ler", write_only=True)

    class Meta(LivroSerializer.Meta):
        fields = ["id", "titulo", "subtitulo", "isbn", "sinopse", "idioma", "paginas", "publicacao", "tipo_capa", "faixa_etaria", "editora", "autores", "autores_nomes", "categoria", "categorias", "capa", "capa_attachment_key", "status"]

    def to_internal_value(self, data):
        import re
        from collections.abc import Mapping
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        data = data.copy()
        if isinstance(data.get("isbn"), str):
            data["isbn"] = re.sub(r"[\s-]+", "", data["isbn"]).upper() or None
        return super().to_internal_value(data)

    def validate_isbn(self, value):
        from rest_framework.exceptions import ValidationError
        if not value:
            return None
        digits = [10 if char == "X" else int(char) for char in value]
        valid = (len(digits) == 10 and sum((10 - i) * digit for i, digit in enumerate(digits)) % 11 == 0)
        valid = valid or (len(digits) == 13 and sum(digit * (1 if i % 2 == 0 else 3) for i, digit in enumerate(digits)) % 10 == 0)
        if not valid:
            raise ValidationError("ISBN inválido. Confira os dígitos do livro.")
        return value

    def create(self, validated_data):
        self.status_escolhido = validated_data.pop("status", "quero_ler")
        return super().create(validated_data)
