from django.conf import settings
from django.core.files.storage import FileSystemStorage, storages


def image_url(image, request=None):
    """Não anuncia arquivos locais ausentes e preserva URLs do storage remoto."""
    if image is None or not image.file:
        return None
    file = image.file
    if isinstance(file.storage, FileSystemStorage) and not file.storage.exists(file.name):
        if "media_fallback" in settings.STORAGES:
            return storages["media_fallback"].url(file.name)
        return None
    try:
        url = file.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url
