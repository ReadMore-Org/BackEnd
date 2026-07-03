from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from core.models import Livro
from core.serializers import LivroSerializer


from core.services.google_books_service import (
    buscar_livro_por_isbn
)


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
