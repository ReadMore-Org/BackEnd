from drf_spectacular.utils import extend_schema

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
    MeSerializer
)


class UserViewSet(ModelViewSet):

    queryset = User.objects.all().order_by('id')

    serializer_class = UserSerializer

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Dados do usuário autenticado",
        description="Retorna os dados do usuário autenticado.",
        responses={200: MeSerializer, 401: None},
    )
    @action(
        detail=False,
        methods=['get', 'patch'],
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):

        user = request.user

        # GET
        if request.method == 'GET':

            serializer = MeSerializer(user)

            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        # PATCH
        serializer = MeSerializer(
            user,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )


class UserRegistrationView(CreateAPIView):

    queryset = User.objects.all()

    serializer_class = UserRegistrationSerializer

    permission_classes = [AllowAny]