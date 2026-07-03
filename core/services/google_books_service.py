import requests

from django.conf import settings

BASE_URL = "https://www.googleapis.com/books/v1/volumes"


def buscar_livro_por_isbn(isbn):

    try:
        print("CHAMOU GOOGLE")
        
        response = requests.get(
            BASE_URL,
            params={
                "q": f"isbn:{isbn}",
                "key": settings.GOOGLE_BOOKS_API_KEY,
            },
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )

        if response.status_code == 429:

            return {
                "erro": "Muitas requisições para a API do Google. Tente novamente em alguns minutos."
            }

        response.raise_for_status()

        data = response.json()

        if data.get("totalItems", 0) == 0:
            return None

        info = data["items"][0]["volumeInfo"]

        return {
            "titulo": info.get("title"),
            "subtitulo": info.get("subtitle"),
            "sinopse": info.get("description"),
            "paginas": info.get("pageCount"),
            "idioma": info.get("language"),
            "data_publicacao": info.get("publishedDate"),
            "thumbnail": info.get("imageLinks", {}).get("thumbnail"),
        }

    except requests.exceptions.RequestException as erro:

        print("ERRO:", erro)

        return None