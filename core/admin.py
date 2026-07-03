from django.contrib.admin import ModelAdmin, register
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _


from core.models import Autor, Categoria, Editora, Livro, User


@register(Autor)
class AutorAdmin(ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    list_filter = ("nome",)
    ordering = ("nome",)
    list_per_page = 10


@register(Categoria)
class CategoriaAdmin(ModelAdmin):
    list_display = ("descricao",)
    search_fields = ("descricao",)
    list_filter = ("descricao",)
    ordering = ("descricao",)
    list_per_page = 10


@register(Editora)
class EditoraAdmin(ModelAdmin):
    list_display = ("nome",)
    search_fields = ("nome",)
    list_filter = ("nome",)
    ordering = ("nome",)
    list_per_page = 10


@register(Livro)
class LivroAdmin(ModelAdmin):
    list_display = (
        "titulo",
        "editora",
    )
    search_fields = ("titulo", "editora__nome", "categoria__descricao")
    list_filter = ("editora", "categoria")
    ordering = ("titulo", "editora", "categoria")
    list_per_page = 25


@register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["id"]
    list_display = ["email", "name"]
    search_fields = ["email", "name", "groups__name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal Info"), {"fields": ("name", "foto", "bio",)}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login",)}),
        (_("Groups"), {"fields": ("groups",)}),
        (_("User Permissions"), {"fields": ("user_permissions",)}),
    )
    readonly_fields = ["last_login"]

from core.models import (
    Autor,
    Categoria,
    Editora,
    Livro,
    User
)



@admin.register(Livro)
class LivroAdmin(admin.ModelAdmin):

    list_display = ['titulo', 'isbn', 'editora']
    search_fields = ['titulo', 'isbn']
    list_filter = ['editora']
    ordering = ['titulo']
    list_per_page = 25


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):

    list_display = ['nome']
    search_fields = ['nome']
    list_filter = ['nome']
    ordering = ['nome']
    list_per_page = 10


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):

    list_display = ['descricao']
    search_fields = ['descricao']
    list_filter = ['descricao']
    ordering = ['descricao']
    list_per_page = 10


@admin.register(Editora)
class EditoraAdmin(admin.ModelAdmin):

    list_display = ['nome']
    search_fields = ['nome']
    list_filter = ['nome']
    ordering = ['nome']
    list_per_page = 10



    add_fieldsets = (
        (
            None,
            {

                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "name",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

