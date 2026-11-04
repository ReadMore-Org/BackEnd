"""Valida capas Google, inclusive placeholders retornados com HTTP 200."""
import hashlib
import json
import math
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from django.core.cache import cache
from PIL import Image, ImageChops, ImageOps, ImageStat, UnidentifiedImageError
import requests

GOOGLE_HOSTS = {'books.google.com', 'books.googleusercontent.com'}
COVER_HOSTS = GOOGLE_HOSTS | {'covers.openlibrary.org'}


class CoverUnavailable(Exception):
    pass


def _safe_url(url):
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname not in COVER_HOSTS or parts.port not in (None, 443)
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


@lru_cache(maxsize=1)
def _local_samples():
    path = Path(__file__).resolve().parents[1] / 'static/core/missing_cover_samples.json'
    return json.loads(path.read_text())


def matches_known_placeholder(image):
    # Mesmo enquadramento dos cartões; exclui botões, bordas e sombras da captura.
    fitted = ImageOps.fit(image.convert('RGB'), (180, 260), Image.Resampling.BILINEAR)
    pixels = list(fitted.crop((14, 65, 166, 234)).resize((24, 32), Image.Resampling.BILINEAR).tobytes())
    for reference in _local_samples():
        n = len(reference)
        if sum(abs(a - b) for a, b in zip(pixels, reference)) / n > 12:
            continue
        sum_a, sum_b = sum(pixels), sum(reference)
        variance_a = n * sum(a * a for a in pixels) - sum_a ** 2
        variance_b = n * sum(b * b for b in reference) - sum_b ** 2
        denominator = math.sqrt(variance_a * variance_b)
        if denominator and (n * sum(a * b for a, b in zip(pixels, reference)) - sum_a * sum_b) / denominator >= 0.9:
            return True
    return image.size == (1, 1)


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


@lru_cache(maxsize=1)
def _placeholder_references():
    # Referências locais: validar uma capa real não deve aguardar downloads
    # de oito imagens de indisponibilidade, nem depender da rede para reconhecê-las.
    folder = Path(__file__).resolve().parents[1] / 'static/core/cover_placeholders'
    references = []
    for name in ('gray.png', 'unavailable.png'):
        with Image.open(folder / name) as image:
            references.append(image.convert('RGB'))
    return references


def get_google_cover(url):
    url = _safe_url(url)
    key = 'google-cover-v4:' + hashlib.sha256(url.encode()).hexdigest()
    cached = cache.get(key)
    if cached is False:
        raise CoverUnavailable()
    if cached is not None:
        return cached
    try:
        content, mime, image = _download(url)
        if matches_known_placeholder(image) or is_placeholder(image, _placeholder_references()):
            # HTTP 404 permite ao componente tentar as outras capas do mesmo livro.
            # A imagem padrão pertence ao último passo do fallback, no frontend.
            cache.set(key, False, 3600)
            raise CoverUnavailable()
        result = (content, mime)
        cache.set(key, result, 86400)
        return result
    except (requests.RequestException, UnidentifiedImageError, OSError, ValueError) as exc:
        cache.set(key, False, 60)
        raise CoverUnavailable() from exc
