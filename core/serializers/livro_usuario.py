from rest_framework.serializers import ModelSerializer, SerializerMethodField
 
from core.models import LivroUsuario
from .livro import LivroRetrieveSerializer
 
 
class LivroUsuarioSerializer(ModelSerializer):
    livro = LivroRetrieveSerializer(read_only=True)
    # Resumo do anúncio (ou None). O front usa isso na página do livro
    # para decidir entre "Enviar ao marketplace" e "Remover do marketplace".
    anuncio = SerializerMethodField()
 
    class Meta:
        model = LivroUsuario
        fields = "__all__"
        read_only_fields = ("usuario",)
 
    def get_anuncio(self, obj):
        anuncio = getattr(obj, "anuncio", None)
        if anuncio is None:
            return None
        return {
            "id": anuncio.id,
            "tipo": anuncio.tipo,
            "condicao": anuncio.condicao,
        }
 
 
class LivroUsuarioWriteSerializer(ModelSerializer):
    class Meta:
        model = LivroUsuario
        fields = ("livro", "status")
 