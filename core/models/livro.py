from django.db import models

from django.core.validators import RegexValidator
from uploader.models import Image

from .autor import Autor
from .categoria import Categoria
from .editora import Editora

isbn_validador = RegexValidator(   
    regex=r'^(?:\d{9}X|\d{10}|\d{13})$',
    message='Código ISBN inválido'
)

class Livro(models.Model):
    
    CLAS_CHOICES = [
        ('livre', 'livre para todos'),
        ('adulto', 'adulto')
    ]
    
    CAPA_CHOICES = [
        ('dura', 'Capa dura'),
        ('mole', 'Capa mole'),
        ('sobre', 'Capa dura com sobrecapa'),
        ('orelhas', 'Capa mole com orelhas')
    ]
    
    titulo = models.CharField(max_length=50)
    subtitulo = models.CharField(max_length=50, blank=True, null=True)
    isbn = models.CharField(max_length=13, validators=[isbn_validador], blank=True, null=True)
    sinopse = models.CharField(max_length=650, blank=True, null=True)
    idioma = models.CharField(max_length=2, blank=True, null=True)
    
    paginas = models.IntegerField(blank=True, null=True)
    avaliacoes = models.IntegerField(blank=True, null=True)
    
    nota = models.DecimalField(decimal_places=1, max_digits=3, null=True, blank=True)
    
    publicacao = models.DateField(verbose_name="data de publicação", blank=True, null=True)
    
    tipo_capa = models.CharField(max_length=45, choices=CAPA_CHOICES, blank=True, null=True)
    faixa_etaria = models.CharField(max_length=45, choices=CLAS_CHOICES, blank=True, null=True)
    
    editora = models.ForeignKey(Editora, on_delete=models.PROTECT, related_name='livro', null=True, blank=True)
    autores = models.ManyToManyField(Autor, related_name='livro', blank=True)
    categoria = models.ManyToManyField(Categoria, related_name='livro', blank=True)
    
    capa = models.ForeignKey(
        Image,
        related_name='+',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
    
    
    