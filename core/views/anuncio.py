from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
 
from core.models import Anuncio
from core.serializers import (
    AnuncioDetailSerializer,
    AnuncioListSerializer,
    AnuncioWriteSerializer,
)
 
 
class AnuncioViewSet(viewsets.ModelViewSet):
    """Marketplace de livros (troca / empréstimo).
 
    GET    /api/anuncios/          lista anúncios de OUTROS usuários
                                   filtros: ?tipo=troca|emprestimo &categoria=<id> &q=<texto>
    GET    /api/anuncios/<id>/     detalhe (livro + dono com email e bio)
    POST   /api/anuncios/          cria {livro_usuario, tipo, condicao, observacao}
    PATCH  /api/anuncios/<id>/     edita (só o dono)
    DELETE /api/anuncios/<id>/     remove (só o dono)
 
    Exige login porque o detalhe expõe o email do dono.
    """
 
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
 
    def get_queryset(self):
        user = self.request.user
 
        queryset = Anuncio.objects.select_related(
            "livro_usuario__livro__capa",
            "livro_usuario__livro__editora",
            "livro_usuario__usuario__foto",
        ).prefetch_related(
            "livro_usuario__livro__autores",
            "livro_usuario__livro__categoria",
        )
 
        # Só o dono edita/remove o próprio anúncio
        if self.action in ("update", "partial_update", "destroy"):
            return queryset.filter(livro_usuario__usuario=user)
 
        # Visível no marketplace apenas enquanto o livro está como lendo/lido
        queryset = queryset.filter(livro_usuario__status__in=["lendo", "lido"])
 
        if self.action == "list":
            queryset = queryset.exclude(livro_usuario__usuario=user)
 
            params = self.request.query_params
            tipo = params.get("tipo")
            categoria = params.get("categoria")
            termo = (params.get("q") or "").strip()
 
            if tipo in ("troca", "emprestimo"):
                queryset = queryset.filter(tipo=tipo)
 
            if categoria and categoria.isdigit():
                queryset = queryset.filter(livro_usuario__livro__categoria__id=categoria)
 
            if termo:
                queryset = queryset.filter(
                    Q(livro_usuario__livro__titulo__icontains=termo)
                    | Q(livro_usuario__livro__autores__nome__icontains=termo)
                )
 
            queryset = queryset.distinct()
 
        return queryset
 
    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return AnuncioWriteSerializer
        if self.action == "retrieve":
            return AnuncioDetailSerializer
        return AnuncioListSerializer
 
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        anuncio = serializer.save()
 
        # Responde já com o formato completo de listagem
        saida = AnuncioListSerializer(
            anuncio, context=self.get_serializer_context()
        )
        return Response(saida.data, status=201)