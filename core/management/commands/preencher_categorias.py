import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import Livro
from core.services.categorias_google import (
    normalizar_categorias_google,
    obter_ou_criar_categoria,
)

BASE_URL = "https://www.googleapis.com/books/v1/volumes"


def buscar_categorias_por_isbn(isbn):
    """Retorna (categorias_brutas, rate_limit). Lista vazia se o Google não tiver."""
    resposta = requests.get(
        BASE_URL,
        params={"q": f"isbn:{isbn}", "key": settings.GOOGLE_BOOKS_API_KEY},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=10,
    )

    if resposta.status_code == 429:
        return [], True

    resposta.raise_for_status()
    itens = resposta.json().get("items") or []
    if not itens:
        return [], False

    return itens[0].get("volumeInfo", {}).get("categories", []), False


class Command(BaseCommand):
    help = (
        "Preenche a categoria dos livros que já estão no banco e não têm nenhuma, "
        "buscando pelo ISBN no Google Books."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--pausa",
            type=float,
            default=0.5,
            help="Segundos de espera entre chamadas ao Google (padrão 0.5)",
        )

    def handle(self, *args, **options):
        livros = Livro.objects.filter(categoria__isnull=True).exclude(isbn__isnull=True)
        total = livros.count()
        self.stdout.write(f"{total} livro(s) sem categoria e com ISBN.")

        preenchidos = 0

        for livro in livros:
            try:
                brutas, limite = buscar_categorias_por_isbn(livro.isbn)
            except requests.RequestException as erro:
                self.stderr.write(f"[erro] {livro.titulo}: {erro}")
                continue

            if limite:
                self.stderr.write(
                    "O Google limitou as requisições (429). Rode o comando de novo mais tarde."
                )
                break

            nomes = normalizar_categorias_google(brutas)
            if not nomes:
                self.stdout.write(f"[sem categoria no Google] {livro.titulo}")
            else:
                livro.categoria.set([obter_ou_criar_categoria(n) for n in nomes])
                preenchidos += 1
                self.stdout.write(f"[ok] {livro.titulo}: {', '.join(nomes)}")

            time.sleep(options["pausa"])

        sem_isbn = Livro.objects.filter(categoria__isnull=True, isbn__isnull=True).count()
        self.stdout.write(self.style.SUCCESS(f"Pronto: {preenchidos} livro(s) preenchido(s)."))
        if sem_isbn:
            self.stdout.write(
                f"{sem_isbn} livro(s) sem ISBN não podem ser buscados automaticamente: "
                "edite a categoria deles no admin."
            )