from datetime import date

from django.core.files.base import ContentFile
import requests

from core.models import Autor, Editora, Livro, LivroUsuario
from core.services.categorias_google import (
    normalizar_categorias_google,
    obter_ou_criar_categoria,
)
from uploader.models import Image


def _get_or_create_editora(nome):
    if not nome:
        return None
    editora, _ = Editora.objects.get_or_create(nome=nome.strip())
    return editora


def _set_categorias(livro, categorias_brutas):
    """Aceita as categorias cruas do Google ("Fiction / Romance / General")."""
    nomes = normalizar_categorias_google(categorias_brutas)
    if not nomes:
        return
    livro.categoria.set([obter_ou_criar_categoria(nome) for nome in nomes])


def _set_autores(livro, autores_dados):
    if not autores_dados:
        return

    autores_objs = []
    
    for item in autores_dados:
        # Se o item for um dicionário, extrai a chave 'nome' ou 'name'
        if isinstance(item, dict):
            nome = item.get("nome") or item.get("name") or ""
        elif isinstance(item, str):
            nome = item
        else:
            nome = str(item) if item else ""

        # Trata a string removendo espaços extras
        nome = nome.strip()

        if nome:
            # Substitua 'Autor' pelo nome do seu Model de Autor
            autor_obj, _ = Autor.objects.get_or_create(nome=nome)
            autores_objs.append(autor_obj)

    # Associa os autores ao livro (M2M)
    livro.autores.set(autores_objs)


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


def importar_livro_google(dados, usuario, status="quero_ler", salvar_na_estante=True):
    isbn = dados.get("isbn") or None
    google_id = dados.get("google_book_id") or None
    livro = Livro.objects.filter(google_book_id=google_id).first() if google_id else None
    if not livro and isbn:
        livro = Livro.objects.filter(isbn=isbn).first()
    if not livro:
        livro = Livro.objects.create(
            google_book_id=google_id,
            titulo=dados.get("titulo", ""),
            subtitulo=dados.get("subtitulo"),
            isbn=isbn,
            sinopse=dados.get("sinopse"),
            idioma=dados.get("idioma"),
            paginas=dados.get("paginas"),

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
    elif not livro.categoria.exists():
        # Livro já existia (criado antes, sem categoria): preenche agora
        _set_categorias(livro, dados.get("categorias", []))

    if google_id and not livro.google_book_id:
        livro.google_book_id = google_id
        livro.save(update_fields=["google_book_id"])

    if not salvar_na_estante:
        return livro

    livro_usuario, criado = LivroUsuario.objects.get_or_create(
        usuario=usuario,
        livro=livro,
        defaults={"status": status},
    )
    if not criado:
        livro_usuario.status = status
        livro_usuario.save()
    return livro_usuario