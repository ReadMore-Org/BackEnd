from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from core.models import Livro, LivroUsuario
from core.serializers import LivroSerializer, LivroUsuarioSerializer, LivroUsuarioWriteSerializer


from core.services.google_books_service import (
    buscar_livro_por_isbn
)
from core.services.google_books_import_service import importar_livro_google


class MeusLivrosAPIView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LivroUsuarioWriteSerializer

        return LivroUsuarioSerializer

    def get_queryset(self):
        queryset = LivroUsuario.objects.filter(
            usuario=self.request.user
        ).select_related("livro")

        status_filtro = self.request.query_params.get("status")

        if status_filtro:
            queryset = queryset.filter(status=status_filtro)

        return queryset

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
    
class MeuLivroDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return LivroUsuarioWriteSerializer

        return LivroUsuarioSerializer

    def get_queryset(self):
        return LivroUsuario.objects.filter(
            usuario=self.request.user
        ).select_related("livro")


class LivroGoogleAPIView(APIView):

    def get(self, request, isbn):

        livro = buscar_livro_por_isbn(isbn)

        if not livro:
            return Response(
                {"erro": "Livro não encontrado"},
                status=404
            )

        if "erro" in livro:
            return Response(
                livro,
                status=429
            )

        return Response(livro)


class LivroViewSet(ModelViewSet):
    queryset = Livro.objects.all()
    serializer_class = LivroSerializer


class ImportarLivroGoogleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        dados = request.data
        status_escolhido = dados.get("status", "quero_ler")

        livro_usuario = importar_livro_google(dados, request.user, status_escolhido)
        serializer = LivroUsuarioSerializer(livro_usuario)

        return Response(serializer.data, status=201)