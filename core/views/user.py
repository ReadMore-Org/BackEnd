from drf_spectacular.utils import extend_schema

import requests
from django.core.files.base import ContentFile

from uploader.models import Image

from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.models import User

from core.serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    MeSerializer,
)


class UserViewSet(ModelViewSet):
    queryset = User.objects.all().order_by("id")

    serializer_class = UserSerializer

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: MeSerializer, 401: None},
    )
    @action(
        detail=False,
        methods=["get", "patch"],
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        user = request.user

        # GET
        if request.method == "GET":
            serializer = MeSerializer(user)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        # PATCH
        serializer = MeSerializer(
            user,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


class UserRegistrationView(CreateAPIView):
    queryset = User.objects.all()

    serializer_class = UserRegistrationSerializer

    permission_classes = [AllowAny]


def save_google_picture(user, picture_url):
    if not picture_url:
        return

    try:
        response = requests.get(
            picture_url,
            timeout=10,
        )

        print("Status download Google:", response.status_code)

        if response.status_code != 200:
            return

        image = Image(
            description=f"Foto Google de {user.email}"
        )

        image.file.save(
            f"user_{user.id}.jpg",
            ContentFile(response.content),
            save=True,
        )

        print("Imagem criada:", image.id)
        print("Arquivo:", image.file.name)

        old_image = user.foto

        user.foto = image

        print("Foto atribuída ao usuário:", user.foto)

        if old_image:
            try:
                if old_image.file:
                    old_image.file.delete(save=False)
            except ValueError:
                pass

            old_image.delete()

    except Exception as e:
        print("Erro ao salvar foto Google:", e)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        access_token = request.data.get("access_token")

        if not access_token:
            return Response(
                {"detail": "Token Google não enviado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # pega dados do usuário Google
        google_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={
                "Authorization": f"Bearer {access_token}"
            },
        )

        if google_response.status_code != 200:
            return Response(
                {"detail": "Token Google inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        google_data = google_response.json()

        email = google_data.get("email")
        name = google_data.get("name")
        picture = google_data.get("picture")

        if not email:
            return Response(
                {"detail": "Google não retornou email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # procura usuário existente
        user = User.objects.filter(email=email).first()

        # cria automaticamente se não existir
        if not user:
            user = User.objects.create(
                email=email,
                name=name,
                google_picture=picture,
            )

            user.set_unusable_password()

            save_google_picture(user, picture)
            print("ANTES DO SAVE:", user.foto)
            user.save()
            print("DEPOIS DO SAVE:", user.foto)

        else:
            if user.google_picture != picture or not user.foto:
                save_google_picture(user, picture)

            user.google_picture = picture

            if not user.name:
                user.name = name
            print("ANTES DO SAVE:", user.foto)
            user.save()
            print("DEPOIS DO SAVE:", user.foto)

        # gera JWT do sistema
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "google_picture": user.google_picture,
                },
            }
        )