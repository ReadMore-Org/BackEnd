"""Normaliza as categorias que vêm do Google Books.

O Google devolve `volumeInfo.categories` como lista de textos em inglês e
hierárquicos, por exemplo:
    ["Fiction / Romance / General", "Juvenile Fiction / Fantasy / Epic"]

Aqui isso vira nomes curtos, em português e sem repetição:
    ["Ficção", "Romance", "Ficção Juvenil", "Fantasia"]

Os nomes que não estão em TRADUCOES são mantidos como vieram (já em português
ou sem tradução). Mantenha esta lista igual à de
FrontEnd/src/utils/categoriasLivro.js.
"""

from core.models import Categoria

# chave em minúsculas
TRADUCOES = {
    "fiction": "Ficção",
    "romance": "Romance",
    "juvenile fiction": "Ficção Juvenil",
    "young adult fiction": "Ficção Jovem Adulto",
    "fantasy": "Fantasia",
    "science fiction": "Ficção Científica",
    "mystery": "Mistério",
    "detective and mystery stories": "Mistério",
    "thrillers": "Suspense",
    "suspense": "Suspense",
    "horror": "Terror",
    "action & adventure": "Ação e Aventura",
    "adventure": "Aventura",
    "action": "Ação",
    "humor": "Humor",
    "comedy": "Comédia",
    "drama": "Drama",
    "poetry": "Poesia",
    "classics": "Clássicos",
    "literary collections": "Coletâneas Literárias",
    "literary criticism": "Crítica Literária",
    "comics & graphic novels": "Quadrinhos",
    "biography & autobiography": "Biografia",
    "history": "História",
    "philosophy": "Filosofia",
    "psychology": "Psicologia",
    "religion": "Religião",
    "self-help": "Autoajuda",
    "business & economics": "Negócios e Economia",
    "social science": "Ciências Sociais",
    "science": "Ciências",
    "technology & engineering": "Tecnologia",
    "computers": "Computação",
    "cooking": "Culinária",
    "travel": "Viagem",
    "art": "Arte",
    "education": "Educação",
    "health & fitness": "Saúde e Bem-estar",
    "body, mind & spirit": "Corpo, Mente e Espírito",
    "family & relationships": "Família e Relacionamentos",
    "true crime": "Crimes Reais",
    "juvenile nonfiction": "Infantojuvenil",
    "political science": "Política",
    "performing arts": "Artes Cênicas",
    "music": "Música",
    "nature": "Natureza",
    "pets": "Animais de Estimação",
    "sports & recreation": "Esportes",
    "games & activities": "Jogos",
    "language arts & disciplines": "Linguagem e Literatura",
    "foreign language study": "Idiomas",
}

# níveis genéricos que não ajudam a navegar
IGNORAR = {"general", "geral", "other", "outros", ""}

MAX_POR_LIVRO = 3
TAMANHO_MAXIMO = 50  # Categoria.descricao tem max_length=50


def normalizar_categorias_google(categorias):
    """Recebe a lista bruta do Google (ou nomes já tratados) e devolve nomes limpos."""
    resultado = []

    for item in categorias or []:
        if isinstance(item, dict):
            item = item.get("descricao") or item.get("nome") or ""
        if not isinstance(item, str):
            continue  # ids numéricos etc. não servem como nome

        for parte in item.split("/"):
            parte = parte.strip()
            if parte.lower() in IGNORAR:
                continue

            nome = TRADUCOES.get(parte.lower(), parte)[:TAMANHO_MAXIMO]
            if nome and nome.lower() not in [r.lower() for r in resultado]:
                resultado.append(nome)

    return resultado[:MAX_POR_LIVRO]


def obter_ou_criar_categoria(nome):
    """Busca sem diferenciar maiúsculas/minúsculas para não duplicar ('Fiction' x 'fiction')."""
    categoria = Categoria.objects.filter(descricao__iexact=nome).first()
    if categoria:
        return categoria
    return Categoria.objects.create(descricao=nome)