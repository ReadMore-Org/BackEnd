"""Busca recomendações no Google e usa um catálogo independente se ele falhar."""
import hashlib
import re
import unicodedata
import threading
import time
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.core.cache import cache

HEADERS = {'User-Agent': 'ReadMore/1.0 (book discovery; Open Library integration)'}
CACHE_SECONDS = 7 * 24 * 60 * 60
_openlibrary_lock = threading.Lock()
_next_openlibrary_request = 0.0


class CatalogUnavailable(Exception):
    def __init__(self, status=503):
        self.status = status


def _normalize(value):
    text = unicodedata.normalize('NFKD', value or '')
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in text if not unicodedata.combining(c)).lower()).strip()


def _matches(title, authors, expected, author):
    actual = _normalize(title)
    base = _normalize(re.split(r'[:–—]', re.sub(r'\s*\([^)]*\)\s*$', '', title or ''))[0])
    words = [w for w in _normalize(author).split() if len(w) > 2 and w not in ('das', 'dos')]
    names = _normalize(' '.join(authors or []))
    return (actual == _normalize(expected) or base == _normalize(expected)) and all(w in names for w in words)


def _get_json(url, params=None):
    if url.startswith('https://openlibrary.org/'):
        # Limita a três consultas por segundo, inclusive entre requisições concorrentes.
        global _next_openlibrary_request
        with _openlibrary_lock:
            now = time.monotonic()
            delay = max(0, _next_openlibrary_request - now)
            _next_openlibrary_request = max(now, _next_openlibrary_request) + 0.35
        if delay:
            time.sleep(delay)
    response = requests.get(url, params=params, headers=HEADERS, timeout=5)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError('Invalid catalog response')
    return data


def _valid_isbn(value):
    value = str(value).replace('-', '').replace(' ', '').upper()
    if re.fullmatch(r'\d{13}', value) and sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(value)) % 10 == 0:
        return value
    if re.fullmatch(r'\d{9}[\dX]', value) and sum((10 - i) * (10 if n == 'X' else int(n)) for i, n in enumerate(value)) % 11 == 0:
        return value
    return None


def _edition_volume(edition, authors):
    # ISBN identifica uma edição real e permite salvá-la sem inventar um ID Google.
    isbn = next((valid for value in edition.get('isbn_13', []) + edition.get('isbn_10', [])
                 if (valid := _valid_isbn(value))), None)
    if not isbn:
        return None
    languages = [value.get('key', '').rsplit('/', 1)[-1] for value in edition.get('languages', [])]
    if languages and 'por' not in languages:
        return None
    description = edition.get('description', '')
    if isinstance(description, dict):
        description = description.get('value', '')
    covers = [cover for cover in edition.get('covers', []) if isinstance(cover, int) and cover > 0]
    cover = f'https://covers.openlibrary.org/b/id/{covers[0]}-L.jpg?default=false' if covers else None
    google_cover = 'https://books.google.com/books/content?' + urlencode({
        'vid': f'ISBN{isbn}', 'printsec': 'frontcover', 'img': 1, 'zoom': 1, 'source': 'gbs_api',
    })
    year = re.search(r'\b\d{4}\b', edition.get('publish_date', ''))
    volume = {
        'id': f'isbn:{isbn}', 'source': 'openlibrary', 'googleCover': google_cover,
        'volumeInfo': {
            'title': edition.get('title', ''), 'subtitle': edition.get('subtitle', ''),
            'authors': authors, 'language': 'pt', 'description': description,
            'industryIdentifiers': [{'type': 'ISBN_13' if len(isbn) == 13 else 'ISBN_10', 'identifier': isbn}],
            'pageCount': edition.get('number_of_pages'),
            'publisher': next(iter(edition.get('publishers', [])), ''),
            'publishedDate': year.group() if year else '',
            'categories': edition.get('subjects', []),
            'imageLinks': {'thumbnail': cover} if cover else {},
        },
    }
    cache.set(f'recommended-isbn:{isbn}', volume, CACHE_SECONDS)
    return volume


def _search_openlibrary(title, author):
    escaped_title = title.replace('\\', '\\\\').replace('"', '\\"')
    data = _get_json('https://openlibrary.org/search.json', {
        'q': f'"{escaped_title}" language:por', 'author': author, 'lang': 'pt', 'limit': 5,
        'fields': 'key,title,author_name,editions,editions.key,editions.title,editions.language',
    })
    for work in data.get('docs', []):
        authors = work.get('author_name', [])
        for edition in work.get('editions', {}).get('docs', []):
            if not _matches(edition.get('title', ''), authors, title, author):
                continue
            key = edition.get('key', '')
            if not re.fullmatch(r'/books/OL\d+M', key):
                continue
            details = _get_json(f'https://openlibrary.org{key}.json')
            if not _matches(details.get('title', ''), authors, title, author):
                continue
            volume = _edition_volume(details, authors)
            if volume:
                return {'items': [volume], 'source': 'openlibrary'}
    return {'items': [], 'source': 'openlibrary'}


def get_recommended_edition(isbn):
    isbn = _valid_isbn(isbn)
    if not isbn:
        raise ValueError('Invalid ISBN')
    cached = cache.get(f'recommended-isbn:{isbn}')
    if cached is not None:
        return cached
    try:
        details = _get_json(f'https://openlibrary.org/isbn/{isbn}.json')
        authors = []
        for ref in details.get('authors', [])[:3]:
            key = ref.get('key', '')
            if re.fullmatch(r'/authors/OL\d+A', key):
                author = _get_json(f'https://openlibrary.org{key}.json')
                if author.get('name'):
                    authors.append(author['name'])
        volume = _edition_volume(details, authors)
        if not volume:
            raise ValueError('Edition unavailable')
        return volume
    except (requests.RequestException, ValueError) as exc:
        raise CatalogUnavailable() from exc


def search_recommended_books(title, author):
    key = 'recommended-volume-v2:' + hashlib.sha256(f'{title}|{author}'.encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    google_error = None
    if not cache.get('recommended-google-unavailable'):
        try:
            data = _get_json('https://www.googleapis.com/books/v1/volumes', {
                'q': f'{title} {author}', 'key': settings.GOOGLE_BOOKS_API_KEY,
                'printType': 'books', 'maxResults': 20, 'langRestrict': 'pt', 'orderBy': 'relevance',
            })
            items = data.get('items', [])
            if not isinstance(items, list):
                raise ValueError('Invalid catalog response')
            matching = [book for book in items if isinstance(book, dict) and book.get('id') and _matches(
                book.get('volumeInfo', {}).get('title', ''), book.get('volumeInfo', {}).get('authors', []), title, author,
            )]
            if matching:
                result = {'items': matching, 'source': 'google'}
                cache.set(key, result, CACHE_SECONDS)
                return result
        except (requests.RequestException, ValueError) as exc:
            google_error = exc
            cache.set('recommended-google-unavailable', True, 60)
    # O bloqueio temporário do Google nunca bloqueia a fonte alternativa.
    try:
        result = _search_openlibrary(title, author)
        if result.get('items'):
            cache.set(key, result, CACHE_SECONDS)
        return result
    except (requests.RequestException, ValueError) as exc:
        status = getattr(getattr(google_error or exc, 'response', None), 'status_code', None) or 503
        raise CatalogUnavailable(status) from exc
