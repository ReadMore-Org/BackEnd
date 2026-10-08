from django.db import models
 
from .livro_usuario import LivroUsuario
 
 
class Anuncio(models.Model):
    """Livro físico que um usuário colocou no marketplace (troca ou empréstimo).
 
    O anúncio é ligado ao LivroUsuario (a estante do usuário):
    - se o livro sair da estante, o anúncio some junto (CASCADE);
    - se o status voltar para "quero_ler", o anúncio deixa de aparecer
      no marketplace (filtro na view) e volta se o status voltar a lendo/lido.
    """
 
    TIPO_CHOICES = [
        ("troca", "Troca"),
        ("emprestimo", "Empréstimo"),
    ]
 
    CONDICAO_CHOICES = [
        ("novo", "Novo"),
        ("bom", "Bom estado"),
        ("regular", "Regular"),
        ("desgastado", "Desgastado"),
    ]
 
    livro_usuario = models.OneToOneField(
        LivroUsuario,
        on_delete=models.CASCADE,
        related_name="anuncio",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    condicao = models.CharField(
        max_length=20, choices=CONDICAO_CHOICES, default="bom"
    )
    observacao = models.CharField(max_length=255, blank=True, default="")
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
 
    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "anúncio"
        verbose_name_plural = "anúncios"
 
    def __str__(self):
        return f"{self.livro_usuario.livro} ({self.get_tipo_display()})"