"""Valida capas Google, inclusive placeholders retornados com HTTP 200."""
import hashlib
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.core.cache import cache
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError
import requests

GOOGLE_HOSTS = {'books.google.com', 'books.googleusercontent.com'}
REFERENCE_URLS = (
    'https://books.google.com/books/content?vid=ISBN0000000000&printsec=frontcover&img=1&zoom=1&source=gbs_api',
    'https://books.google.com/googlebooks/images/no_cover_thumb.gif',
)


class CoverUnavailable(Exception):
    pass


def _safe_url(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname not in GOOGLE_HOSTS or parts.port not in (None, 443)
                or parts.username or parts.password or len(url) > 2048):
            raise ValueError('Invalid image URL')
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(parse_qsl(parts.query))), ''))
    except (TypeError, ValueError) as exc:
        raise CoverUnavailable() from exc


def _download(url):
    for _ in range(3):
        url = _safe_url(url)
        response = requests.get(url, timeout=5, allow_redirects=False)
        if response.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, response.headers.get('Location', ''))
            continue
        response.raise_for_status()
        if not response.content or len(response.content) > 4 * 1024 * 1024:
            raise CoverUnavailable()
        with Image.open(BytesIO(response.content)) as image:
            image.load()
            if image.width > 4096 or image.height > 4096:
                raise CoverUnavailable()
            mime = Image.MIME.get(image.format)
            if mime not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'):
                raise CoverUnavailable()
            return response.content, mime, image.convert('RGB')
    raise CoverUnavailable()


def is_placeholder(image, references):
    # Compara o conteúdo, nunca apenas as dimensões (também usadas por capas reais).
    sample = image.resize((64, 64), Image.Resampling.LANCZOS)
    for reference in references:
        if abs(image.width / image.height - reference.width / reference.height) > 0.03:
            continue
        difference = ImageChops.difference(sample, reference.resize((64, 64), Image.Resampling.LANCZOS))
        if max(ImageStat.Stat(difference).mean) <= 1.0 and max(high for low, high in difference.getextrema()) <= 24:
            return True
    return False


def _placeholder_references():
    key = 'google-cover-placeholder-references-v1'
    stored = cache.get(key)
    if stored is None:
        stored = []
        for url in REFERENCE_URLS:
            try:
                content, _, _ = _download(url)
                stored.append(content)
            except (requests.RequestException, CoverUnavailable, UnidentifiedImageError, OSError, ValueError):
                continue
        cache.set(key, stored, 86400 if stored else 60)
    references = []
    for content in stored:
        with Image.open(BytesIO(content)) as image:
            references.append(image.convert('RGB'))
    return references


def get_google_cover(url):
    url = _safe_url(url)
    key = 'google-cover-v1:' + hashlib.sha256(url.encode()).hexdigest()
    cached = cache.get(key)
    if cached is False:
        raise CoverUnavailable()
    if cached is not None:
        return cached
    try:
        content, mime, image = _download(url)
        if is_placeholder(image, _placeholder_references()):
            result = ((Path(__file__).resolve().parents[1] / 'static/core/livro_sem_capa.png').read_bytes(), 'image/png')
            cache.set(key, result, 3600)
            return result
        result = (content, mime)
        cache.set(key, result, 86400)
        return result
    except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
        cache.set(key, False, 60)
        raise CoverUnavailable() from exc
