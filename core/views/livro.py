from rest_framework import generics
from rest_framework.decorators import action
from django.db.models import Avg, Count, Q
from core.models import InteracaoLivro
from core.serializers.social import InteracaoLivroSerializer, ImportarInteracaoSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from core.models import Livro, LivroUsuario
from core.serializers import LivroSerializer, LivroUsuarioSerializer, LivroUsuarioWriteSerializer


from core.services.google_books_service import (
    buscar_livro_por_isbn
)
from core.services.google_books_import_service import importar_livro_google


class MeusLivrosViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = LivroUsuario.objects.all()
    http_method_names = ['get', 'patch', 'post', 'delete']

    serializer_class = LivroUsuarioSerializer


    def get_serializer_class(self):
        if self.action in {'create', 'partial_update', 'update'}:
            return LivroUsuarioWriteSerializer

        return LivroUsuarioSerializer

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

    def get_queryset(self):
        usuario = self.request.user
        queryset = LivroUsuario.objects.filter(
            usuario=usuario
        ).select_related("livro")
        

        return queryset

# class MeusLivrosAPIView(generics.ListCreateAPIView):
#     permission_classes = [IsAuthenticated]

#     def get_serializer_class(self):
#         if self.request.method == "POST":
#             return LivroUsuarioWriteSerializer

#         return LivroUsuarioSerializer

#     def get_queryset(self):
#         queryset = LivroUsuario.objects.filter(
#             usuario=self.request.user
#         ).select_related("livro")

#         status_filtro = self.request.query_params.get("status")

#         if status_filtro:
#             queryset = queryset.filter(status=status_filtro)

#         return queryset

#     def perform_create(self, serializer):
#         serializer.save(usuario=self.request.user)
    
# class MeuLivroDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
#     permission_classes = [IsAuthenticated]

#     def get_serializer_class(self):
#         if self.request.method in ["PATCH", "PUT"]:
#             return LivroUsuarioWriteSerializer

#         return LivroUsuarioSerializer

#     def get_queryset(self):
#         return LivroUsuario.objects.filter(
#             usuario=self.request.user
#         ).select_related("livro")


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
    queryset = Livro.objects.all().order_by("id")
    serializer_class = LivroSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        isbn = self.request.query_params.get("isbn")
        google_id = self.request.query_params.get("google_book_id")
        if google_id:
            return queryset.filter(google_book_id=google_id)
        return queryset.filter(isbn=isbn) if isbn else queryset

    @action(detail=False, methods=["post"], url_path="cadastrar-manual", permission_classes=[IsAuthenticated])
    def cadastrar_manual(self, request):
        from django.db import transaction
        from core.serializers.livro import CadastroManualSerializer
        serializer = CadastroManualSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            livro = serializer.save()
            vinculo = LivroUsuario.objects.create(usuario=request.user, livro=livro, status=serializer.status_escolhido)
            return Response({
                "livro": LivroSerializer(livro, context=self.get_serializer_context()).data,
                "livro_usuario": LivroUsuarioSerializer(vinculo, context=self.get_serializer_context()).data,
            }, status=201)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def avaliacoes(self, request):
        # Consulta em lote para os cards do catálogo externo, sem importar livros.
        google_ids = request.query_params.get("google_ids", "").split(",")
        isbns = request.query_params.get("isbns", "").split(",")
        ids = [value for value in request.query_params.get("ids", "").split(",") if value.isdigit()]
        if max(len(google_ids), len(isbns), len(ids)) > 100:
            return Response({"detail": "Consulte até 100 livros por vez."}, status=400)
        queryset = Livro.objects.filter(
            Q(google_book_id__in=[value for value in google_ids if value])
            | Q(isbn__in=[value for value in isbns if value])
            | Q(id__in=ids)
        ).annotate(media=Avg("interacoes__nota"), total=Count("interacoes__nota"))
        return Response(list(queryset.values("id", "google_book_id", "isbn", "media", "total")))

    @action(detail=False, methods=["post"], url_path="importar-interacao", permission_classes=[IsAuthenticated])
    def importar_interacao(self, request):
        serializer = ImportarInteracaoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        livro = importar_livro_google(request.data, request.user, salvar_na_estante=False)
        return Response(LivroSerializer(livro, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["get", "patch"], permission_classes=[IsAuthenticated])
    def interacao(self, request, pk=None):
        livro = self.get_object()
        interacao = InteracaoLivro.objects.filter(usuario=request.user, livro=livro).first()
        if request.method == "PATCH":
            serializer = InteracaoLivroSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            interacao, _ = InteracaoLivro.objects.update_or_create(usuario=request.user, livro=livro, defaults=serializer.validated_data)
        resumo = livro.interacoes.filter(nota__isnull=False).aggregate(media=Avg("nota"), total=Count("id"))
        return Response({"favorito": interacao.favorito if interacao else False, "nota": interacao.nota if interacao else None, **resumo})


class ImportarLivroGoogleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        dados = request.data
        status_escolhido = dados.get("status", "quero_ler")

        livro_usuario = importar_livro_google(dados, request.user, status_escolhido)
        serializer = LivroUsuarioSerializer(livro_usuario)

        return Response(serializer.data, status=201)