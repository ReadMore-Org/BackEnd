"""Descoberta por gostos explícitos, sem depender de histórico ou avaliações."""
import hashlib
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q

from core.models import Livro
from core.services.recommendations import _get_json, _normalize, CACHE_SECONDS
from core.services.categorias_google import normalizar_categorias_google


def _catalog_books(query):
    key = 'reading-discovery-v1:' + hashlib.sha256(query.encode()).hexdigest()
    stored = cache.get(key)
    if stored is not None:
        return stored, False
    if cache.get('recommended-google-unavailable'):
        return [], True
    try:
        data = _get_json('https://www.googleapis.com/books/v1/volumes', {
            'q': query, 'key': settings.GOOGLE_BOOKS_API_KEY,
            'printType': 'books', 'langRestrict': 'pt', 'maxResults': 20,
        })
        items = []
        for book in data.get('items', []):
            info = book.get('volumeInfo', {})
            title, authors = info.get('title', ''), info.get('authors', [])
            if not book.get('id') or not title or not authors or info.get('language') not in (None, 'pt'):
                continue
            if any(word in _normalize(title + ' ' + info.get('subtitle', '')) for word in ('study guide', 'resumo', 'guia de estudo')):
                continue
            if len(title) > 260 or len(authors[0]) > 150:
                continue
            items.append(book)
            # Reutiliza o resultado na consulta por obra, sem outra chamada externa.
            work_key = 'recommended-volume-v2:' + hashlib.sha256(f'{title}|{authors[0]}'.encode()).hexdigest()
            cache.set(work_key, {'items': [book], 'source': 'google'}, CACHE_SECONDS)
        cache.set(key, items, 3600 if items else 60)
        return items, False
    except (requests.RequestException, ValueError, TypeError):
        return [], True


def _local_books(filter_query):
    return Livro.objects.filter(filter_query).prefetch_related('autores', 'categoria').order_by('id').distinct()[:30]


def discover_books(query):
    local = _local_books(Q(titulo__icontains=query) | Q(autores__nome__icontains=query))
    books = [{
        'id': str(book.id), 'source': 'local', 'title': book.titulo,
        'authors': [author.nome for author in book.autores.all()], 'isbn': book.isbn,
    } for book in local]
    external, unavailable = _catalog_books(query)
    for book in external:
        info = book['volumeInfo']
        isbn = next((value['identifier'] for value in info.get('industryIdentifiers', [])
                     if value.get('type') in ('ISBN_13', 'ISBN_10') and value.get('identifier')), None)
        books.append({'id': book['id'], 'source': 'google', 'title': info['title'], 'authors': info['authors'], 'isbn': isbn})
    seen = set()
    unique = []
    for book in books:
        identity = (_normalize(book['title']), _normalize(' '.join(book['authors'])))
        if identity not in seen:
            unique.append(book)
            seen.add(identity)
    return {'books': unique[:30], 'external_unavailable': unavailable}


def personalized_entries(preferences):
    authors = list(dict.fromkeys(preferences.get('authors', []) + [
        author for book in preferences.get('books', []) for author in book.get('authors', [])
    ]))
    categories = preferences.get('categories', [])
    if not authors and not categories:
        return []
    filters = Q()
    for author in authors:
        filters |= Q(autores__nome__iexact=author)
    for category in categories:
        for label in normalizar_categorias_google([category]):
            filters |= Q(categoria__descricao__iexact=label)
    entries = []
    if filters:
        for book in _local_books(filters):
            names = list(book.autores.all())
            if names:
                entries.append([book.titulo, names[0].nome])
    # Consultas limitadas e concorrentes; o catálogo editorial continua disponível
    # quando as fontes externas não respondem.
    queries = [f'inauthor:"{author.replace(chr(34), " ")}"' for author in authors[:2]]
    queries += [f'subject:"{category.replace(chr(34), " ")}"' for category in categories[:2]]
    queries = queries[:3]
    if queries:
        with ThreadPoolExecutor(max_workers=3) as executor:
            for items, _ in executor.map(_catalog_books, queries):
                for book in items:
                    info = book['volumeInfo']
                    entries.append([info['title'], info['authors'][0]])
    unique = []
    seen = set()
    for title, author in entries:
        key = (_normalize(title), _normalize(author))
        if key not in seen:
            unique.append([title, author])
            seen.add(key)
    return unique[:60]
