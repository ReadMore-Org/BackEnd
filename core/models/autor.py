from django.db import models


class Autor(models.Model):
    nome = models.CharField(max_length=50)

    class Meta:
        verbose_name = "autor"
        verbose_name_plural = "autores"

    def __str__(self):
        return self.nome
