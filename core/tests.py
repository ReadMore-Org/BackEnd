from django.test import TestCase
from rest_framework.test import APIClient
from core.models import User, Livro, LivroUsuario, Anuncio, AvaliacaoUsuario, InteracaoLivro


class SocialAPITests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana@example.com', 'password123', name='Ana', bio='Leitora')
        self.bia = User.objects.create_user('bia@example.com', 'password123', name='Bia')
        self.caio = User.objects.create_user('caio@example.com', 'password123', name='Caio')
        self.livro = Livro.objects.create(titulo='Livro de teste')
        self.client = APIClient()
        self.client.force_authenticate(self.ana)

    def test_user_rating_updates_instead_of_duplicating_and_averages(self):
        url = f'/api/usuarios/{self.bia.id}/avaliar/'
        self.assertEqual(self.client.post(url, {'nota': 5}).status_code, 200)
        self.assertEqual(self.client.post(url, {'nota': 3}).data['minha_nota'], 3)
        self.assertEqual(AvaliacaoUsuario.objects.count(), 1)
        self.client.force_authenticate(self.caio)
        response = self.client.post(url, {'nota': 5})
        self.assertEqual(response.data['media'], 4)
        self.assertEqual(response.data['total'], 2)
        self.client.force_authenticate(self.ana)
        response = self.client.get(f'/api/usuarios/{self.bia.id}/perfil/')
        self.assertEqual(response.data['minha_nota'], 3)
        self.assertEqual(response.data['media'], 4)

    def test_self_rating_and_out_of_range_rejected(self):
        self.assertEqual(self.client.post(f'/api/usuarios/{self.ana.id}/avaliar/', {'nota': 5}).status_code, 400)
        for nota in [0, 6, -1, 2.5, 'abc', None]:
            self.assertEqual(self.client.post(f'/api/usuarios/{self.bia.id}/avaliar/', {'nota': nota}, format='json').status_code, 400)
        self.assertFalse(AvaliacaoUsuario.objects.exists())

    def test_favorites_and_book_ratings_persist_and_are_private(self):
        url = f'/api/livros/{self.livro.id}/interacao/'
        self.assertEqual(self.client.get(url).data['favorito'], False)
        self.assertEqual(self.client.patch(url, {'favorito': True, 'nota': 5}, format='json').status_code, 200)
        self.assertEqual(self.client.get(url).data['nota'], 5)
        favorites = self.client.get('/api/usuarios/favoritos/').data
        self.assertEqual(favorites[0]['livro']['id'], self.livro.id)
        self.assertFalse(LivroUsuario.objects.exists())
        self.client.force_authenticate(self.bia)
        self.assertEqual(self.client.get('/api/usuarios/favoritos/').data, [])
        self.assertIsNone(self.client.get(url).data['nota'])
        self.assertEqual(self.client.patch(url, {'nota': 3}, format='json').data['media'], 4)
        self.client.force_authenticate(self.ana)
        self.assertEqual(self.client.patch(url, {'favorito': False}, format='json').data['nota'], 5)
        self.assertEqual(self.client.get('/api/usuarios/favoritos/').data, [])
        self.assertEqual(InteracaoLivro.objects.count(), 2)
        self.assertEqual(self.client.get(f'/api/livros/{self.livro.id}/').data['nota'], 4)

    def test_invalid_book_ratings_do_not_write(self):
        for nota in [0, 6, 1.5]:
            response = self.client.patch(f'/api/livros/{self.livro.id}/interacao/', {'nota': nota}, format='json')
            self.assertEqual(response.status_code, 400)
        self.assertFalse(InteracaoLivro.objects.exists())

    def test_profile_only_exposes_public_fields_and_visible_ads(self):
        shelf = LivroUsuario.objects.create(usuario=self.bia, livro=self.livro, status='lido')
        Anuncio.objects.create(livro_usuario=shelf, tipo='troca')
        url = f'/api/usuarios/{self.bia.id}/perfil/'
        data = self.client.get(url).data
        self.assertEqual(data['email'], self.bia.email)
        self.assertEqual(len(data['livros']), 1)
        self.assertEqual(len(data['anuncios']), 1)
        for field in ['password', 'is_superuser', 'groups', 'is_staff', 'last_login']:
            self.assertNotIn(field, data)
        shelf.status = 'quero_ler'
        shelf.save()
        self.assertEqual(self.client.get(url).data['anuncios'], [])

    def test_search_and_other_profile_cannot_be_edited(self):
        response = self.client.get('/api/usuarios/', {'search': 'Bia'})
        self.assertEqual([u['id'] for u in response.data['results']], [self.bia.id])
        self.assertIn(self.client.patch(f'/api/usuarios/{self.bia.id}/', {'name': 'Alterado'}).status_code, [403, 405])
        self.assertEqual(self.client.post('/api/usuarios/', {'email': 'new@example.com'}).status_code, 405)
        self.bia.refresh_from_db()
        self.assertEqual(self.bia.name, 'Bia')
        self.assertEqual(self.client.patch('/api/usuarios/me/', {'bio': 'Nova bio'}).status_code, 200)

    def test_authentication_required(self):
        self.client.force_authenticate(None)
        for url in ['/api/usuarios/', '/api/usuarios/favoritos/', f'/api/usuarios/{self.bia.id}/perfil/', f'/api/livros/{self.livro.id}/interacao/']:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post(f'/api/usuarios/{self.bia.id}/avaliar/', {'nota': 5}).status_code, 401)

    def test_book_lookup_by_isbn(self):
        self.livro.isbn = '9781234567890'
        self.livro.save()
        Livro.objects.create(titulo='Outro')
        response = self.client.get('/api/livros/', {'isbn': self.livro.isbn})
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], self.livro.id)

    def test_google_favorite_import_is_stable_without_isbn_or_shelf(self):
        payload = {'google_book_id': 'google-volume-123', 'titulo': 'Livro Google', 'autores': ['Autora'], 'editora': 'Editora', 'categorias': ['Ficção']}
        url = '/api/livros/importar-interacao/'
        first = self.client.post(url, payload, format='json')
        self.assertEqual(first.status_code, 200)
        second = self.client.post(url, payload, format='json')
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertFalse(LivroUsuario.objects.exists())
        book_id = first.data['id']
        self.client.patch(f'/api/livros/{book_id}/interacao/', {'favorito': True}, format='json')
        found = self.client.get('/api/livros/', {'google_book_id': payload['google_book_id']}).data['results']
        self.assertEqual(found[0]['id'], book_id)
        self.assertTrue(self.client.get(f'/api/livros/{book_id}/interacao/').data['favorito'])

    def test_google_favorite_import_preserves_existing_reading_status(self):
        self.livro.isbn = '9781234567890'
        self.livro.save()
        shelf = LivroUsuario.objects.create(usuario=self.ana, livro=self.livro, status='lido')
        response = self.client.post('/api/livros/importar-interacao/', {'google_book_id': 'existing-google-volume', 'titulo': self.livro.titulo, 'isbn': self.livro.isbn}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], self.livro.id)
        shelf.refresh_from_db()
        self.assertEqual(shelf.status, 'lido')
        self.assertEqual(LivroUsuario.objects.count(), 1)

    def test_missing_user_or_book_returns_404(self):
        self.assertEqual(self.client.get('/api/usuarios/99999/perfil/').status_code, 404)
        self.assertEqual(self.client.post('/api/usuarios/99999/avaliar/', {'nota': 5}).status_code, 404)
        self.assertEqual(self.client.patch('/api/livros/99999/interacao/', {'favorito': True}, format='json').status_code, 404)

    def test_book_summary_never_uses_google_or_legacy_rating(self):
        self.livro.nota = 4.9
        self.livro.avaliacoes = 9999
        self.livro.google_book_id = 'rated-google-volume'
        self.livro.save()
        data = self.client.get(f'/api/livros/{self.livro.id}/').data
        self.assertIsNone(data['nota'])
        self.assertEqual(data['avaliacoes'], 0)
        data = self.client.get('/api/livros/avaliacoes/', {'google_ids': self.livro.google_book_id}).data
        self.assertIsNone(data[0]['media'])
        self.assertEqual(data[0]['total'], 0)

    def test_all_visitors_see_the_readmore_average_and_editing_does_not_add_votes(self):
        url = f'/api/livros/{self.livro.id}/interacao/'
        for first, second, expected in [(5, 5, 5), (2, 2, 2), (5, 1, 3)]:
            self.client.force_authenticate(self.ana)
            self.client.patch(url, {'nota': first}, format='json')
            self.client.force_authenticate(self.bia)
            self.client.patch(url, {'nota': second}, format='json')
            self.client.force_authenticate(self.caio)
            data = self.client.get(f'/api/livros/{self.livro.id}/').data
            self.assertEqual(data['nota'], expected)
            self.assertEqual(data['avaliacoes'], 2)
            summary = self.client.get('/api/livros/avaliacoes/', {'ids': self.livro.id}).data[0]
            self.assertEqual(summary['media'], expected)
            self.assertEqual(summary['total'], 2)
        self.client.force_authenticate(self.ana)
        self.client.patch(url, {'nota': None}, format='json')
        summary = self.client.get('/api/livros/avaliacoes/', {'ids': self.livro.id}).data[0]
        self.assertEqual(summary['media'], 1)
        self.assertEqual(summary['total'], 1)

    def test_rating_summary_is_public_matches_isbn_and_does_not_import_books(self):
        self.livro.isbn = '9781234567890'
        self.livro.save()
        InteracaoLivro.objects.create(usuario=self.ana, livro=self.livro, nota=5)
        self.client.force_authenticate(None)
        response = self.client.get('/api/livros/avaliacoes/', {'isbns': self.livro.isbn})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['media'], 5)
        self.assertEqual(response.data[0]['total'], 1)
        self.assertEqual(self.client.get('/api/livros/avaliacoes/', {'google_ids': 'not-imported'}).data, [])
        self.assertEqual(Livro.objects.count(), 1)


class GoogleCategoryTests(TestCase):
    def test_translates_subgenres_and_preserves_more_categories(self):
        from core.services.categorias_google import normalizar_categorias_google
        self.assertEqual(normalizar_categorias_google([
            'Fiction / Science Fiction / Cyberpunk', 'Fiction / Fantasy / Epic', 'General'
        ]), ['Ficção', 'Ficção Científica', 'Cyberpunk', 'Fantasia', 'Épico'])
        self.assertEqual(normalizar_categorias_google([
            'Comics & Graphic Novels / Manga', 'Biography & Autobiography / Personal Memoirs'
        ]), ['Quadrinhos', 'Mangá', 'Biografia', 'Memórias Pessoais'])
        result = normalizar_categorias_google([
            'Fiction', 'Fantasy', 'Epic', 'Adventure', 'Friendship', 'School & Education', 'Humor', 'Coming of Age', 'Romance'
        ])
        self.assertEqual(len(result), 8)
        self.assertIn('Amadurecimento', result)

    def test_import_saves_translated_categories(self):
        from core.services.google_books_import_service import importar_livro_google
        user = User.objects.create_user('categories@example.com', 'password123')
        book = importar_livro_google({
            'titulo': 'Programação', 'google_book_id': 'category-import',
            'categorias': ['Computers / Programming Languages / Python', 'Computers / Artificial Intelligence'],
        }, user, salvar_na_estante=False)
        self.assertSetEqual(set(book.categoria.values_list('descricao', flat=True)), {
            'Computação', 'Linguagens de Programação', 'Python', 'Inteligência Artificial',
        })

    def test_book_detail_includes_category_names_without_category_list_lookup(self):
        from core.models import Categoria
        category = Categoria.objects.create(descricao='Fantasia')
        book = Livro.objects.create(titulo='Livro com categoria')
        book.categoria.add(category)
        response = APIClient().get(f'/api/livros/{book.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['categorias'], ['Fantasia'])
        self.assertEqual(response.data['categoria'], [category.id])


class ManualBookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('manual@example.com', 'password123')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = '/api/livros/cadastrar-manual/'
        self.payload = {'titulo': 'Livro manual', 'autores_nomes': ['Autora'], 'status': 'lendo', 'tipo_capa': 'mole', 'faixa_etaria': 'livre'}

    def test_creates_book_and_shelf_together_with_selected_status(self):
        from core.models import Categoria
        category = Categoria.objects.create(descricao='Fantasia')
        response = self.client.post(self.url, {**self.payload, 'isbn': '9780306406157', 'categoria': [category.id], 'nota': 5}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        book = Livro.objects.get()
        self.assertEqual(book.autores.get().nome, 'Autora')
        self.assertEqual(book.categoria.get(), category)
        self.assertIsNone(book.nota)
        self.assertEqual(LivroUsuario.objects.get().status, 'lendo')
        self.assertEqual(LivroUsuario.objects.get().usuario, self.user)
        self.assertEqual(response.data['livro_usuario']['livro']['id'], book.id)

    def test_invalid_fields_do_not_save_book_or_shelf(self):
        for patch in [{'titulo': ' '}, {'autores_nomes': []}, {'autores_nomes': ['A' * 51]}, {'isbn': '9780306406158'}, {'paginas': 0}, {'paginas': 1.5}, {'publicacao': '2025-02-30'}, {'status': 'outro'}, {'tipo_capa': 'papel'}, {'faixa_etaria': '18'}, {'editora': 99999}, {'categoria': [99999]}]:
            response = self.client.post(self.url, {**self.payload, **patch}, format='json')
            self.assertEqual(response.status_code, 400, (patch, response.data))
        self.assertFalse(Livro.objects.exists())
        self.assertFalse(LivroUsuario.objects.exists())

    def test_duplicate_isbn_returns_field_error(self):
        payload = {**self.payload, 'isbn': '9780306406157'}
        self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 201)
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('isbn', response.data)
        self.assertEqual(Livro.objects.count(), 1)

    def test_transaction_rolls_back_book_and_authors_if_shelf_fails(self):
        from unittest.mock import patch
        from core.models import Autor
        with patch('core.views.livro.LivroUsuario.objects.create', side_effect=RuntimeError('falha')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, self.payload, format='json')
        self.assertFalse(Livro.objects.exists())
        self.assertFalse(Autor.objects.exists())

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 401)

    def test_isbn_normalization_and_optional_fields(self):
        response = self.client.post(self.url, {**self.payload, 'isbn': '978-0-306-40615-7', 'paginas': None, 'editora': None}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Livro.objects.get().isbn, '9780306406157')

    def test_malformed_body_returns_validation_error(self):
        response = self.client.post(self.url, [], format='json')
        self.assertEqual(response.status_code, 400)
