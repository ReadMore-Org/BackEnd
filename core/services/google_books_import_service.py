from datetime import date

from django.core.files.base import ContentFile
import requests

from core.models import Autor, Categoria, Editora, Livro, LivroUsuario
from uploader.models import Image


def _get_or_create_editora(nome):
    if not nome:
        return None
    editora, _ = Editora.objects.get_or_create(nome=nome.strip())
    return editora


def _set_categorias(livro, nomes):
    if not nomes:
        return
    categorias = []
    for nome in nomes:
        nome = (nome or "").strip()
        if not nome:
            continue
        categoria, _ = Categoria.objects.get_or_create(descricao=nome)
        categorias.append(categoria)
    livro.categoria.set(categorias)


def _set_autores(livro, nomes):
    if not nomes:
        return
    autores = []
    for nome in nomes:
        nome = (nome or "").strip()
        if not nome:
            continue
        autor, _ = Autor.objects.get_or_create(nome=nome)
        autores.append(autor)
    livro.autores.set(autores)


def _baixar_capa(capa_url, descricao=""):
    if not capa_url:
        return None
    try:
        response = requests.get(capa_url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    filename = capa_url.split("/")[-1].split("?")[0] or "capa.jpg"
    imagem = Image(description=descricao)
    imagem.file.save(filename, ContentFile(response.content), save=True)
    return imagem


def _parse_data_publicacao(valor):
    """O Google Books pode mandar '1997', '1997-06' ou '1997-06-26'."""
    if not valor:
        return None

    partes = valor.split("-")

    try:
        if len(partes) == 1:
            return date(int(partes[0]), 1, 1)
        if len(partes) == 2:
            return date(int(partes[0]), int(partes[1]), 1)
        if len(partes) == 3:
            return date(int(partes[0]), int(partes[1]), int(partes[2]))
    except (ValueError, TypeError):
        return None

    return None


def importar_livro_google(dados, usuario, status="quero_ler"):
    isbn = dados.get("isbn") or None

    livro = Livro.objects.filter(isbn=isbn).first() if isbn else None

    if not livro:
        livro = Livro.objects.create(
            titulo=dados.get("titulo", ""),
            subtitulo=dados.get("subtitulo"),
            isbn=isbn,
            sinopse=dados.get("sinopse"),
            idioma=dados.get("idioma"),
            paginas=dados.get("paginas"),
            avaliacoes=dados.get("avaliacoes"),
            nota=dados.get("nota"),
            publicacao=_parse_data_publicacao(dados.get("publicacao")),
            editora=_get_or_create_editora(dados.get("editora")),
        )

        _set_autores(livro, dados.get("autores", []))
        _set_categorias(livro, dados.get("categorias", []))

        capa_url = dados.get("capa")
        if capa_url:
            imagem = _baixar_capa(capa_url, descricao=livro.titulo)
            if imagem:
                livro.capa = imagem
                livro.save()

    livro_usuario, criado = LivroUsuario.objects.get_or_create(
        usuario=usuario,
        livro=livro,
        defaults={"status": status},
    )

    if not criado:
        livro_usuario.status = status
        livro_usuario.save()

    return livro_usuario