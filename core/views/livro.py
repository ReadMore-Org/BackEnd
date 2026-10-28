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

    @action(detail=False, methods=["get"], url_path="capa-google", permission_classes=[AllowAny])
    def capa_google(self, request):
        from django.http import HttpResponse
        from core.services.book_covers import get_google_cover, CoverUnavailable
        try:
            content, mime = get_google_cover(request.query_params.get("url", ""))
            response = HttpResponse(content, content_type=mime)
            response["Cache-Control"] = "public, max-age=86400"
            response["X-Content-Type-Options"] = "nosniff"
            return response
        except CoverUnavailable:
            return Response({"detail": "Capa indisponível."}, status=404)

    @action(detail=False, methods=["get"], url_path="catalogo-edicao", permission_classes=[AllowAny])
    def catalogo_edicao(self, request):
        from core.services.recommendations import get_recommended_edition, CatalogUnavailable
        try:
            return Response(get_recommended_edition(request.query_params.get("isbn", "")))
        except ValueError:
            return Response({"detail": "Informe um ISBN válido."}, status=400)
        except CatalogUnavailable:
            return Response({"detail": "Não foi possível carregar esta edição agora."}, status=503)

    @action(detail=False, methods=["get"], url_path="catalogo-recomendados", permission_classes=[AllowAny])
    def catalogo_recomendados(self, request):
        from core.services.recommendations import search_recommended_books, CatalogUnavailable
        title = request.query_params.get("titulo", "").strip()
        author = request.query_params.get("autor", "").strip()
        if not title or not author or len(title) > 260 or len(author) > 150:
            return Response({"detail": "Informe título e autor válidos."}, status=400)
        try:
            return Response(search_recommended_books(title, author))
        except CatalogUnavailable as exc:
            return Response({"detail": "Catálogo externo temporariamente indisponível."}, status=exc.status)

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def recomendados(self, request):
        # Consulta apenas o catálogo persistido: funciona mesmo sem Google Books.
        titulos = request.query_params.getlist("titulo")
        if not titulos or len(titulos) > 120 or any(len(titulo) > 260 for titulo in titulos):
            return Response({"detail": "Informe de 1 a 120 títulos válidos."}, status=400)
        filtro = Q()
        for titulo in titulos:
            if titulo.strip():
                filtro |= Q(titulo__istartswith=titulo.strip()) | Q(titulo__startswith=titulo.strip().upper())
        if not filtro:
            return Response([])
        livros = Livro.objects.filter(filtro).select_related("capa").prefetch_related(
            "autores", "categoria"
        ).annotate(total_leitores=Count("usuarios", distinct=True)).order_by("-total_leitores", "id")[:240]
        return Response(self.get_serializer(livros, many=True).data)

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