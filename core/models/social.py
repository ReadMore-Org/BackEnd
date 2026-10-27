from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models


class AvaliacaoUsuario(models.Model):
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avaliacoes_feitas")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="avaliacoes_recebidas")
    nota = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["autor", "usuario"], name="avaliacao_usuario_unica"),
            models.CheckConstraint(condition=models.Q(nota__gte=1, nota__lte=5), name="nota_usuario_valida"),
            models.CheckConstraint(condition=~models.Q(autor=models.F("usuario")), name="sem_autoavaliacao"),
        ]


class InteracaoLivro(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interacoes_livros")
    livro = models.ForeignKey("core.Livro", on_delete=models.CASCADE, related_name="interacoes")
    favorito = models.BooleanField(default=False)
    nota = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["usuario", "livro"], name="interacao_livro_unica"),
            models.CheckConstraint(condition=models.Q(nota__isnull=True) | models.Q(nota__gte=1, nota__lte=5), name="nota_livro_valida"),
        ]
