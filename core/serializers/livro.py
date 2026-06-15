from rest_framework.serializers import (
    ModelSerializer,
    SlugRelatedField,
    ListField,
    CharField,
)

from uploader.models import Image
from uploader.serializers import ImageSerializer

from core.serializers.autor import AutorSerializer
from core.models import Livro, Autor


class LivroRetrieveSerializer(ModelSerializer):
    capa = ImageSerializer(required=False)

    class Meta:
        model = Livro
        fields = "__all__"
        depth = 1


class LivroSerializer(ModelSerializer):
    autores = AutorSerializer(many=True, read_only=True)
    autores_nomes = ListField(
        child=CharField(max_length=50),
        write_only=True,
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
        livro = Livro.objects.create(**validated_data)
        self._set_autores(livro, autores_nomes)
        return livro

    def update(self, instance, validated_data):
        autores_nomes = validated_data.pop("autores_nomes", None)
        livro = super().update(instance, validated_data)
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