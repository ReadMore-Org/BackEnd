from django.contrib import admin
from django.urls import include, path
from django.conf import settings

from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from uploader.router import router as uploader_router


from core.views import (
    UserRegistrationView,
    UserViewSet,
    GoogleLoginView,
    EditoraViewSet,
    CategoriaViewSet,
    AutorViewSet,
    LivroViewSet,
)

from core.views.livro import LivroGoogleAPIView, ImportarLivroGoogleAPIView, MeusLivrosAPIView


router = DefaultRouter()

router.register(r"usuarios", UserViewSet, basename="usuarios")
router.register(r"editoras", EditoraViewSet, basename="editoras")
router.register(r"categorias", CategoriaViewSet, basename="categorias")
router.register(r"autores", AutorViewSet, basename="autores")
router.register(r"livros", LivroViewSet, basename="livros")


urlpatterns = [
    path("admin/", admin.site.urls),
    # OpenAPI 3
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/doc/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Autenticação JWT
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Registro de usuários
    path("api/registro/", UserRegistrationView.as_view(), name="user_registration"),
    path("api/google-login/", GoogleLoginView.as_view(), name="google_login"),
    # API

    path(
        "api/google-books/<str:isbn>/",
        LivroGoogleAPIView.as_view()
    ),
    path(
        "api/livros/importar-google/",
        ImportarLivroGoogleAPIView.as_view()
    ),
    path("api/livros-usuario/", MeusLivrosAPIView.as_view(), name="meus-livros"),
    path("api/livros-usuario/<int:pk>/", MeusLivrosAPIView.as_view(), name="meus-livros-detail"), 

    path('api/', include(router.urls)),
    path('api/uploads/', include(uploader_router.urls)),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)