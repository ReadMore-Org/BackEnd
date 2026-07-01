"""
Django admin customization.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

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


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Define the admin pages for users."""

    ordering = ['id']

    list_display = ['email', 'name']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),

        (_('Personal Info'), {
            'fields': ('name',)
        }),

        (_('Permissions'), {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
            )
        }),

        (_('Important dates'), {
            'fields': ('last_login',)
        }),

        (_('Groups'), {
            'fields': ('groups',)
        }),

        (_('User Permissions'), {
            'fields': ('user_permissions',)
        }),
    )

    readonly_fields = ['last_login']

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),

                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'name',
                    'is_active',
                    'is_staff',
                    'is_superuser',
                ),
            },
        ),
    )