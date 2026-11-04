from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import User, Livro, Autor, Categoria
from core.services.reading_preferences import personalized_entries, discover_books


class ReadingPreferencesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('preferences@example.com')
        self.other = User.objects.create_user('other@example.com')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = '/api/usuarios/preferencias-leitura/'

    def tearDown(self):
        cache.clear()

    def test_pending_by_default_save_empty_skip_and_edit_are_persisted_per_account(self):
        me = self.client.get('/api/usuarios/me/').data
        self.assertEqual(me['reading_preferences_status'], 'pending')
        payload = {'status': 'completed', 'categories': ['fantasy', 'fantasy'], 'authors': ['Tolkien'],
                   'books': [{'title': 'O Hobbit', 'authors': ['Tolkien'], 'id': 'abc', 'source': 'google'}]}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.reading_preferences['categories'], ['fantasy'])
        self.assertEqual(self.user.reading_preferences_status, 'completed')
        fresh = APIClient()
        fresh.force_authenticate(self.user)
        self.assertEqual(fresh.get('/api/usuarios/me/').data['reading_preferences'], response.data['reading_preferences'])
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/usuarios/me/').data['reading_preferences_status'], 'pending')
        self.client.force_authenticate(self.user)
        response = self.client.post(self.url, {'status': 'skipped'}, format='json')
        self.assertEqual(response.data['reading_preferences'], {'categories': [], 'authors': [], 'books': []})
        self.assertEqual(response.data['reading_preferences_status'], 'skipped')
        response = self.client.post(self.url, {'status': 'completed'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reading_preferences_status'], 'completed')

    def test_authentication_validation_and_privacy(self):
        self.assertEqual(APIClient().post(self.url, {'status': 'skipped'}, format='json').status_code, 401)
        for payload in [{'status': 'pending'}, {'status': 'completed', 'authors': ['a' * 151]},
                        {'status': 'completed', 'categories': 'fantasy'},
                        {'status': 'completed', 'books': [{'title': 'Bad', 'authors': 'name'}]}]:
            self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 400)
        public = self.client.get(f'/api/usuarios/{self.other.id}/').data
        self.assertNotIn('reading_preferences', public)
        self.assertEqual(self.client.get('/api/usuarios/descobrir-leituras/', {'q': 'x'}).status_code, 400)

    def test_local_discovery_still_works_if_google_is_unavailable(self):
        book = Livro.objects.create(titulo='Histórias de exemplo')
        book.autores.add(Autor.objects.create(nome='Autora Teste'))
        with patch('core.services.reading_preferences._catalog_books', return_value=([], True)):
            response = self.client.get('/api/usuarios/descobrir-leituras/', {'q': 'Autora'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['books'][0]['title'], book.titulo)
            self.assertTrue(response.data['external_unavailable'])

    def test_personalization_uses_categories_authors_and_authors_of_favorite_books(self):
        fantasy = Livro.objects.create(titulo='Uma fantasia')
        fantasy.categoria.add(Categoria.objects.create(descricao='Fantasia'))
        fantasy.autores.add(Autor.objects.create(nome='Autora Fantasia'))
        related = Livro.objects.create(titulo='Outra história')
        related.autores.add(Autor.objects.create(nome='Autora Favorita'))
        with patch('core.services.reading_preferences._catalog_books', return_value=([], True)):
            entries = personalized_entries({'categories': ['fantasy'], 'authors': [],
                'books': [{'title': 'Favorito', 'authors': ['Autora Favorita']}]})
        self.assertIn(['Uma fantasia', 'Autora Fantasia'], entries)
        self.assertIn(['Outra história', 'Autora Favorita'], entries)
        self.user.reading_preferences_status = 'skipped'
        self.user.save()
        with patch('core.services.reading_preferences.personalized_entries') as discover:
            self.assertEqual(self.client.get('/api/usuarios/recomendacoes-preferencias/').data, [])
            discover.assert_not_called()

    def test_external_discovery_is_cached_and_reuses_real_volume_for_recommendations(self):
        data = {'items': [{'id': 'real-volume', 'volumeInfo': {'title': 'História real', 'authors': ['Autora'], 'language': 'pt'}}]}
        with patch('core.services.reading_preferences._get_json', return_value=data) as fetch:
            first = discover_books('Autora')
            second = discover_books('Autora')
            self.assertEqual(first, second)
            fetch.assert_called_once()
        from core.services.recommendations import search_recommended_books
        with patch('core.services.recommendations._get_json', side_effect=AssertionError('Já está em cache')):
            self.assertEqual(search_recommended_books('História real', 'Autora')['items'][0]['id'], 'real-volume')
