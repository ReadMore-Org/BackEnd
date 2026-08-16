from django.conf import settings
from django.db import models

from .livro import Livro


class LivroUsuario(models.Model):
    STATUS_CHOICES = [
        ("quero_ler", "Quero ler"),
        ("lendo", "Lendo"),
        ("lido", "Lido"),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="livros_usuario",
    )
    livro = models.ForeignKey(Livro, on_delete=models.CASCADE, related_name="usuarios")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, blank=True, null=True)
    adicionado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("usuario", "livro")

    def __str__(self):
        return f"{self.usuario} - {self.livro} ({self.status})"