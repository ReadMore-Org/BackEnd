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

from core.views import UserRegistrationView, UserViewSet, EditoraViewSet, CategoriaViewSet, AutorViewSet, LivroViewSet
from core.views.livro import LivroGoogleAPIView

router = DefaultRouter()

router.register(r'usuarios', UserViewSet, basename='usuarios')
router.register(r'editoras', EditoraViewSet, basename='editoras')
router.register(r'categorias', CategoriaViewSet, basename='categorias')
router.register(r'autores', AutorViewSet, basename='autores')
router.register(r'livros', LivroViewSet, basename='livros')


urlpatterns = [
    path('admin/', admin.site.urls),
    # OpenAPI 3
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path(
        'api/doc/',
        SpectacularSwaggerView.as_view(url_name='schema'),
        name='swagger-ui',
    ),
    path(
        'api/redoc/',
        SpectacularRedocView.as_view(url_name='schema'),
        name='redoc',
    ),
    # Autenticação JWT
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    # Registro de usuários
    path('api/registro/', UserRegistrationView.as_view(), name='user_registration'),
    # API
    path('api/', include(router.urls)),
    path('api/uploads/', include(uploader_router.urls)),
    
    
    path(
        "api/google-books/<str:isbn>/",
        LivroGoogleAPIView.as_view()
    ),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

