from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from core.models import Anuncio, Livro, LivroUsuario

PASSWORD = "senha-forte-123"

# PNG 1x1 válido: o tipo real é detectado pelo conteúdo (libmagic), nunca pela extensão.
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


def make_user(email, name=None, **extra):
    return get_user_model().objects.create_user(
        email=email, password=PASSWORD, name=name, **extra
    )


def make_anuncio(owner, titulo="Dom Casmurro", tipo="troca", status="lido"):
    """Anúncio do marketplace de `owner` (o livro precisa estar como lendo/lido para aparecer)."""
    livro = Livro.objects.create(titulo=titulo)
    livro_usuario = LivroUsuario.objects.create(
        usuario=owner, livro=livro, status=status
    )

    return Anuncio.objects.create(livro_usuario=livro_usuario, tipo=tipo)


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)

    return client


def token_for(user):
    return str(AccessToken.for_user(user))
