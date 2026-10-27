# 🌚 BackEnd do ReadMore
## Repositório do BackEnd do Readmore

### Perfis, avaliações e favoritos

Os endpoints abaixo exigem JWT e usam o usuário autenticado para salvar notas e favoritos:

- `GET /api/usuarios/?search=nome-ou-email&page=1`: busca paginada de leitores, com os campos públicos do perfil.
- `GET /api/usuarios/{id}/perfil/`: nome, email, foto, biografia, estante, anúncios visíveis, média, total de avaliações e nota do visitante.
- `POST /api/usuarios/{id}/avaliar/` com `{"nota": 1}` até `5`: cria ou atualiza uma avaliação por autor; autoavaliações são rejeitadas.
- `GET /api/usuarios/favoritos/`: favoritos somente do usuário autenticado.
- `GET /api/livros/{id}/interacao/`: favorito, nota pessoal e resumo das avaliações do livro.
- `PATCH /api/livros/{id}/interacao/` com `{"favorito": true}` e/ou `{"nota": 5}`: altera apenas os campos enviados. `nota: null` remove a avaliação pessoal.
- `POST /api/livros/importar-interacao/`: importa os dados de um livro Google (`google_book_id` e `titulo` obrigatórios) para avaliar/favoritar, sem criar ou alterar a estante. O volume é reaproveitado pelo ID Google ou ISBN.

As notas são inteiros de 1 a 5, com validação na API e restrições no banco. Favoritos são independentes do status de leitura. As notas dos livros são exclusivamente a média das avaliações do ReadMore; sem votos locais, `nota` é `null` e `avaliacoes` é `0`, mesmo que existam notas antigas ou do Google nos metadados. Perfis de terceiros são somente leitura; edições pessoais continuam em `/api/usuarios/me/`.

Aplique as migrações `0021` e `0022` com `python manage.py migrate`. Para validar: `python manage.py test core`. Em instalações PDM com pacotes locais, prefixe os comandos com `PYTHONPATH=__pypackages__/3.12/lib`.

### Arquivos de imagem no desenvolvimento

No modo `DEVELOPMENT`, os arquivos são lidos de `media/`, enquanto o banco guarda os caminhos. Se o banco veio de outra instalação, copie também os arquivos de mídia correspondentes: os registros não contêm os bytes das fotos. Quando `CLOUDINARY_URL` está configurado no desenvolvimento, a API tenta a URL do Cloudinary para arquivos ausentes localmente, mantendo os novos uploads em disco. Sem essa alternativa configurada, retorna `url: null`, permitindo ao front usar a foto Google, a capa pelo ISBN ou uma imagem padrão. URLs de storages remotos são preservadas. Testes desse comportamento: `python manage.py test uploader`.


`GET /api/livros/avaliacoes/?google_ids=volume1,volume2&isbns=isbn1,isbn2&ids=1,2` consulta publicamente as médias e quantidades de votos do ReadMore em lote (até 100 identificadores por grupo). O endpoint não importa livros do Google e não inclui notas externas nem votos nulos. Cada usuário tem um voto por livro: editar a nota substitui o voto anterior.


O Explore oferece 40 filtros de categoria, com busca dentro da lista. O dicionário de categorias do Google Books contém 258 traduções sincronizadas entre `FrontEnd/src/utils/categoriasLivro.js` e `BackEnd/core/services/categorias_google.py`. A normalização preserva até 8 categorias por livro, traduz subgêneros, remove níveis genéricos e mantém nomes ainda não traduzidos. Os filtros comparam segmentos completos para distinguir, por exemplo, ciências de ficção científica e ficção de não ficção.
Testes de tradução e persistência das categorias na importação: `python manage.py test core.tests.GoogleCategoryTests`.


`POST /api/livros/cadastrar-manual/` exige autenticação, título e `autores_nomes` (lista não vazia, até 50 caracteres por autor). Aceita os campos da edição, IDs de categorias/editora e `capa_attachment_key`; `status` aceita `quero_ler`, `lendo` ou `lido`. O cadastro cria livro, autores/categorias associados e vínculo com a estante em uma transação. A resposta 201 contém `livro` e `livro_usuario`; falhas de validação retornam 400 com erros por campo. ISBNs são normalizados e validados pelo dígito verificador e unicidade. A nota não é um campo de cadastro. Uploads de imagem aceitam JPG/PNG de até 5 MB. Não há migração nova para esse endpoint.
