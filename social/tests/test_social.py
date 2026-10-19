import io
import tempfile
from pathlib import Path
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from social.models import Post, Follow, Like, Comment, Bookmark

User = get_user_model()
PASSWORD = 'Chuva!Caderno739'

def account(username, **kwargs):
    return User.objects.create_user(username=username, name=username.title(), email=f'{username}@example.com', password=PASSWORD, **kwargs)

def photo(name='photo.png', size=(32, 40)):
    output = io.BytesIO()
    Image.new('RGB', size, (70, 160, 120)).save(output, 'PNG')
    return SimpleUploadedFile(name, output.getvalue(), content_type='image/png')

class SocialTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = account('ana')
        cls.bia = account('bia')
        cls.cai = account('cai')
        cls.own = Post.objects.create(author=cls.ana, content='Minha própria publicação')
        cls.followed = Post.objects.create(author=cls.bia, content='Ideia da Bia')
        cls.other = Post.objects.create(author=cls.cai, content='Ideia do Cai')

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.force_login(self.ana)

    def csrf_client(self, logged=False):
        client = APIClient(enforce_csrf_checks=True)
        if logged:
            client.force_login(self.ana)
        client.get('/api/auth/csrf/')
        client.credentials(HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        return client

    def test_all_private_endpoints_require_authentication(self):
        guest = APIClient()
        for method, url in [('get', '/api/me/'), ('patch', '/api/me/'), ('get', '/api/posts/'),
                            ('post', '/api/posts/'), ('get', '/api/posts/feed/'), ('get', '/api/posts/saved/'),
                            ('put', f'/api/posts/{self.followed.pk}/like/'), ('get', '/api/users/'),
                            ('put', '/api/users/bia/follow/'), ('post', '/api/me/password/')]:
            with self.subTest(method=method, url=url):
                self.assertEqual(getattr(guest, method)(url).status_code, 403)

    def test_api_root_exposes_rest_resources(self):
        self.assertEqual(set(self.client.get('/api/').data), {'users', 'posts'})

    def test_registration_logs_in_and_hashes_password(self):
        guest = self.csrf_client()
        result = guest.post('/api/auth/register/', {'username': 'Nova_Pessoa', 'name': 'Nova Pessoa',
                            'email': 'NOVA@EXAMPLE.COM', 'password': PASSWORD, 'password_confirm': PASSWORD}, format='json')
        self.assertEqual(result.status_code, 201)
        new = User.objects.get(username='nova_pessoa')
        self.assertEqual(new.email, 'nova@example.com')
        self.assertNotEqual(new.password, PASSWORD)
        self.assertTrue(new.check_password(PASSWORD))
        self.assertEqual(guest.get('/api/me/').data['id'], new.pk)
        self.assertNotIn('password', result.data)

    def test_registration_requires_csrf_even_for_anonymous(self):
        guest = APIClient(enforce_csrf_checks=True)
        self.assertEqual(guest.post('/api/auth/register/', {}, format='json').status_code, 403)

    def test_registration_rejects_weak_password(self):
        guest = self.csrf_client()
        result = guest.post('/api/auth/register/', {'username': 'novo', 'name': 'Novo', 'email': 'novo@example.com', 'password': '123', 'password_confirm': '123'}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertFalse(User.objects.filter(username='novo').exists())

    def test_registration_rejects_mismatched_passwords(self):
        guest = self.csrf_client()
        result = guest.post('/api/auth/register/', {'username': 'novo', 'name': 'Novo', 'email': 'novo@example.com', 'password': PASSWORD, 'password_confirm': 'different'}, format='json')
        self.assertEqual(result.status_code, 400)
        self.assertIn('password_confirm', result.data)

    def test_registration_rejects_duplicates_ignoring_case(self):
        guest = self.csrf_client()
        for username, email in [('ANA', 'different@example.com'), ('different', 'ANA@EXAMPLE.COM')]:
            result = guest.post('/api/auth/register/', {'username': username, 'name': 'Nome', 'email': email, 'password': PASSWORD, 'password_confirm': PASSWORD}, format='json')
            self.assertEqual(result.status_code, 400)

    def test_registration_rejects_invalid_username(self):
        guest = self.csrf_client()
        for username in ['ab', 'nome com espaco', 'com-hifen', 'x' * 21]:
            result = guest.post('/api/auth/register/', {'username': username, 'name': 'Nome', 'email': 'new@example.com', 'password': PASSWORD, 'password_confirm': PASSWORD}, format='json')
            self.assertEqual(result.status_code, 400)

    def test_login_uses_session_and_accepts_uppercase_username(self):
        guest = self.csrf_client()
        result = guest.post('/api/auth/login/', {'username': 'ANA', 'password': PASSWORD}, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(guest.get('/api/me/').data['username'], 'ana')

    def test_login_rejects_invalid_credentials_and_inactive_account(self):
        self.ana.is_active = False
        self.ana.save(update_fields=['is_active'])
        for username, password in [('bia', 'incorrect'), ('unknown', PASSWORD), ('ana', PASSWORD)]:
            guest = self.csrf_client()
            self.assertEqual(guest.post('/api/auth/login/', {'username': username, 'password': password}, format='json').status_code, 400)

    def test_login_anonymous_csrf_is_enforced(self):
        guest = APIClient(enforce_csrf_checks=True)
        self.assertEqual(guest.post('/api/auth/login/', {'username': 'ana', 'password': PASSWORD}, format='json').status_code, 403)

    def test_login_is_throttled(self):
        guest = self.csrf_client()
        codes = [guest.post('/api/auth/login/', {'username': 'ana', 'password': 'wrong'}, format='json').status_code for _ in range(16)]
        self.assertEqual(codes[-1], 429)

    def test_logout_clears_session(self):
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/me/').status_code, 403)

    def test_session_write_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.ana)
        self.assertEqual(client.post('/api/posts/', {'content': 'Blocked'}, format='json').status_code, 403)
        client.get('/api/auth/csrf/')
        client.credentials(HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(client.post('/api/posts/', {'content': 'Allowed'}, format='json').status_code, 201)

    def test_empty_profile_patch_preserves_every_field(self):
        result = self.client.patch('/api/me/', {}, format='json')
        self.assertEqual(result.status_code, 200)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.name, 'Ana')
        self.assertTrue(self.ana.check_password(PASSWORD))

    def test_name_only_change_does_not_require_password_or_avatar(self):
        result = self.client.patch('/api/me/', {'name': 'Ana Maria'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.name, 'Ana Maria')
        self.assertTrue(self.ana.check_password(PASSWORD))
        self.assertFalse(self.ana.avatar)

    def test_profile_cannot_escalate_privileges_or_change_identity(self):
        self.client.patch('/api/me/', {'is_staff': True, 'is_superuser': True, 'id': self.bia.pk,
                                      'username': 'hacked', 'email': 'hacked@example.com', 'password': 'plain'}, format='json')
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.is_staff)
        self.assertFalse(self.ana.is_superuser)
        self.assertEqual(self.ana.username, 'ana')
        self.assertTrue(self.ana.check_password(PASSWORD))

    def test_bio_can_be_cleared_without_other_changes(self):
        self.client.patch('/api/me/', {'bio': 'Um pouco sobre mim'}, format='json')
        result = self.client.patch('/api/me/', {'bio': ''}, format='json')
        self.assertEqual(result.data['bio'], '')
        self.assertEqual(result.data['name'], 'Ana')

    def test_profile_field_limits(self):
        for data in [{'name': ''}, {'name': 'x' * 81}, {'bio': 'x' * 161}]:
            self.assertEqual(self.client.patch('/api/me/', data, format='json').status_code, 400)

    def test_password_change_keeps_current_session_and_invalidates_others(self):
        other = APIClient()
        other.force_login(self.ana)
        result = self.client.post('/api/me/password/', {'current_password': PASSWORD, 'new_password': 'Outra!SenhaNova842', 'password_confirm': 'Outra!SenhaNova842'}, format='json')
        self.assertEqual(result.status_code, 200)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password('Outra!SenhaNova842'))
        self.assertEqual(self.client.get('/api/me/').status_code, 200)
        self.assertEqual(other.get('/api/me/').status_code, 403)

    def test_invalid_password_change_preserves_password(self):
        for data in [
            {'current_password': 'wrong', 'new_password': 'Outra!SenhaNova842', 'password_confirm': 'Outra!SenhaNova842'},
            {'current_password': PASSWORD, 'new_password': '123', 'password_confirm': '123'},
            {'current_password': PASSWORD, 'new_password': 'Outra!SenhaNova842', 'password_confirm': 'different'},
        ]:
            self.assertEqual(self.client.post('/api/me/password/', data, format='json').status_code, 400)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.check_password(PASSWORD))

    def test_public_profiles_never_expose_credentials_email_or_admin_flags(self):
        fields = self.client.get('/api/users/bia/').data
        for key in ['email', 'password', 'is_staff', 'is_superuser', 'last_login']:
            self.assertNotIn(key, fields)

    def test_other_profile_cannot_be_updated(self):
        self.assertEqual(self.client.patch('/api/users/bia/', {'name': 'Alterado'}, format='json').status_code, 405)
        self.bia.refresh_from_db()
        self.assertEqual(self.bia.name, 'Bia')

    def test_follow_is_idempotent(self):
        for _ in range(2):
            result = self.client.put('/api/users/bia/follow/')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.data['followers_count'], 1)
            self.assertTrue(result.data['is_following'])
        self.assertEqual(Follow.objects.count(), 1)

    def test_cannot_follow_self_or_missing_user(self):
        self.assertEqual(self.client.put('/api/users/ana/follow/').status_code, 400)
        self.assertEqual(self.client.put('/api/users/missing/follow/').status_code, 404)
        self.assertEqual(Follow.objects.count(), 0)

    def test_followers_and_following_lists_match_direction(self):
        Follow.objects.create(follower=self.ana, following=self.bia)
        self.assertEqual([u['username'] for u in self.client.get('/api/users/ana/following/').data['results']], ['bia'])
        self.assertEqual([u['username'] for u in self.client.get('/api/users/bia/followers/').data['results']], ['ana'])
        self.assertEqual(self.client.get('/api/users/ana/followers/').data['count'], 0)

    def test_unfollow_is_idempotent_and_updates_counts(self):
        Follow.objects.create(follower=self.ana, following=self.bia)
        for _ in range(2):
            result = self.client.delete('/api/users/bia/follow/')
            self.assertFalse(result.data['is_following'])
            self.assertEqual(result.data['followers_count'], 0)

    def test_feed_excludes_own_and_unfollowed_posts(self):
        Follow.objects.create(follower=self.ana, following=self.bia)
        feed = self.client.get('/api/posts/feed/').data
        self.assertEqual([post['id'] for post in feed['results']], [self.followed.pk])

    def test_feed_empty_without_following_anyone(self):
        self.assertEqual(self.client.get('/api/posts/feed/').data['count'], 0)

    def test_unfollow_immediately_removes_posts_from_feed(self):
        self.client.put('/api/users/bia/follow/')
        self.assertEqual(self.client.get('/api/posts/feed/').data['count'], 1)
        self.client.delete('/api/users/bia/follow/')
        self.assertEqual(self.client.get('/api/posts/feed/').data['count'], 0)

    def test_feed_ignores_author_query_that_could_bypass_follow_filter(self):
        Follow.objects.create(follower=self.ana, following=self.bia)
        feed = self.client.get('/api/posts/feed/?author=cai').data
        self.assertEqual([post['author']['username'] for post in feed['results']], ['bia'])

    def test_explore_contains_all_active_authors(self):
        self.assertEqual(self.client.get('/api/posts/').data['count'], 3)

    def test_search_users_and_posts(self):
        self.assertEqual(self.client.get('/api/users/?search=BI').data['results'][0]['username'], 'bia')
        self.assertEqual(self.client.get('/api/posts/?search=da%20Bia').data['results'][0]['id'], self.followed.pk)

    def test_suggestions_exclude_self_followed_and_inactive_users(self):
        self.client.put('/api/users/bia/follow/')
        self.assertEqual([u['username'] for u in self.client.get('/api/users/suggestions/').data['results']], ['cai'])
        self.cai.is_active = False
        self.cai.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/users/suggestions/').data['count'], 0)

    def test_profile_post_filter(self):
        result = self.client.get('/api/posts/?author=ana').data
        self.assertEqual([item['id'] for item in result['results']], [self.own.pk])

    def test_create_post_assigns_logged_author_and_rejects_spoofing(self):
        result = self.client.post('/api/posts/', {'content': '  Uma ideia  ', 'author': self.bia.pk}, format='json')
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data['author']['id'], self.ana.pk)
        self.assertEqual(result.data['content'], 'Uma ideia')

    def test_post_content_must_have_1_to_280_characters(self):
        for text in ['', '   ', 'x' * 281]:
            self.assertEqual(self.client.post('/api/posts/', {'content': text}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/posts/', {'content': 'x' * 280}, format='json').status_code, 201)

    def test_owner_can_patch_and_replace_post(self):
        path = f'/api/posts/{self.own.pk}/'
        self.assertEqual(self.client.patch(path, {'content': 'Editado'}, format='json').status_code, 200)
        self.assertEqual(self.client.put(path, {'content': 'Substituído'}, format='json').status_code, 200)
        self.own.refresh_from_db()
        self.assertEqual(self.own.content, 'Substituído')

    def test_cannot_edit_or_delete_someone_elses_post(self):
        path = f'/api/posts/{self.followed.pk}/'
        self.assertEqual(self.client.patch(path, {'content': 'Ataque'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(path).status_code, 403)
        self.followed.refresh_from_db()
        self.assertEqual(self.followed.content, 'Ideia da Bia')

    def test_owner_delete_cascades_related_interactions(self):
        Comment.objects.create(author=self.bia, post=self.own, content='Comentário')
        Like.objects.create(user=self.bia, post=self.own)
        Bookmark.objects.create(user=self.bia, post=self.own)
        self.assertEqual(self.client.delete(f'/api/posts/{self.own.pk}/').status_code, 204)
        self.assertEqual(Comment.objects.count() + Like.objects.count() + Bookmark.objects.count(), 0)

    def test_like_and_unlike_are_idempotent(self):
        path = f'/api/posts/{self.followed.pk}/like/'
        for _ in range(2):
            result = self.client.put(path)
            self.assertTrue(result.data['is_liked'])
            self.assertEqual(result.data['likes_count'], 1)
        for _ in range(2):
            result = self.client.delete(path)
            self.assertFalse(result.data['is_liked'])
            self.assertEqual(result.data['likes_count'], 0)

    def test_unlike_does_not_remove_other_users_like(self):
        Like.objects.create(user=self.bia, post=self.followed)
        self.client.delete(f'/api/posts/{self.followed.pk}/like/')
        self.assertEqual(Like.objects.count(), 1)

    def test_comment_creation_uses_authenticated_author(self):
        result = self.client.post(f'/api/posts/{self.followed.pk}/comments/', {'content': 'Gostei!', 'author': self.cai.pk, 'post': self.own.pk}, format='json')
        self.assertEqual(result.status_code, 201)
        item = Comment.objects.get(pk=result.data['id'])
        self.assertEqual(item.author_id, self.ana.pk)
        self.assertEqual(item.post_id, self.followed.pk)

    def test_comment_content_limits(self):
        for text in ['', '   ', 'x' * 281]:
            self.assertEqual(self.client.post(f'/api/posts/{self.followed.pk}/comments/', {'content': text}, format='json').status_code, 400)

    def test_only_comment_author_can_edit_and_delete(self):
        item = Comment.objects.create(author=self.bia, post=self.own, content='Comentário da Bia')
        path = f'/api/comments/{item.pk}/'
        self.assertEqual(self.client.patch(path, {'content': 'Alterado'}, format='json').status_code, 403)
        self.assertEqual(self.client.delete(path).status_code, 403)
        self.client.force_login(self.bia)
        self.assertEqual(self.client.patch(path, {'content': 'Revisado'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 204)

    def test_post_counts_are_not_multiplied_by_joins(self):
        for user in [self.ana, self.bia]:
            Like.objects.create(user=user, post=self.followed)
            Comment.objects.create(author=user, post=self.followed, content='Comentário')
        data = self.client.get(f'/api/posts/{self.followed.pk}/').data
        self.assertEqual((data['likes_count'], data['comments_count']), (2, 2))

    def test_bookmarks_are_private_and_idempotent(self):
        path = f'/api/posts/{self.followed.pk}/bookmark/'
        self.client.put(path)
        self.client.put(path)
        self.assertEqual(Bookmark.objects.count(), 1)
        self.assertEqual(self.client.get('/api/posts/saved/').data['count'], 1)
        self.client.force_login(self.bia)
        self.assertEqual(self.client.get('/api/posts/saved/').data['count'], 0)
        self.assertFalse(self.client.get(f'/api/posts/{self.followed.pk}/').data['is_saved'])

    def test_unsave_does_not_remove_other_users_saved_posts(self):
        Bookmark.objects.create(user=self.bia, post=self.followed)
        self.client.delete(f'/api/posts/{self.followed.pk}/bookmark/')
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_missing_resources_return_404(self):
        for path in ['/api/posts/999999/', '/api/users/missing/', '/api/comments/999999/', '/api/posts/999999/comments/']:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_pagination_is_stable_and_does_not_duplicate_items(self):
        for number in range(25):
            Post.objects.create(author=self.bia, content=f'Post {number}')
        seen = []
        url = '/api/posts/'
        while url:
            data = self.client.get(url).data
            seen.extend(post['id'] for post in data['results'])
            url = data['next']
        self.assertEqual(len(seen), 28)
        self.assertEqual(len(set(seen)), 28)

    def test_feed_uses_newest_first_with_stable_tie_breaker(self):
        Follow.objects.create(follower=self.ana, following=self.bia)
        posts = [Post.objects.create(author=self.bia, content=f'Mesmo instante {n}') for n in range(18)]
        Post.objects.filter(pk__in=[post.pk for post in posts]).update(created_at=self.followed.created_at)
        result = self.client.get('/api/posts/feed/').data
        self.assertEqual([post['id'] for post in result['results']], sorted([post.pk for post in posts], reverse=True)[:15])

    def test_inactive_users_are_not_discoverable(self):
        self.bia.is_active = False
        self.bia.save(update_fields=['is_active'])
        self.assertEqual(self.client.get('/api/users/bia/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/posts/{self.followed.pk}/').status_code, 404)

    def test_database_rejects_duplicate_like_and_self_follow(self):
        Like.objects.create(user=self.ana, post=self.followed)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Like.objects.create(user=self.ana, post=self.followed)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Follow.objects.create(follower=self.ana, following=self.ana)

    def test_demo_is_repeatable_and_has_no_login_password(self):
        call_command('seed_demo', stdout=io.StringIO())
        call_command('seed_demo', stdout=io.StringIO())
        self.assertEqual(User.objects.count(), 7)
        self.assertEqual(Post.objects.count(), 15)
        self.assertFalse(User.objects.get(username='clara_design').has_usable_password())

    def test_anonymous_pages_redirect_to_login(self):
        self.client.logout()
        for path in ['/', '/explorar/', '/salvos/', '/perfil/ana/', '/configuracoes/', f'/post/{self.own.pk}/']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 302)
            self.assertTrue(result.url.startswith('/entrar/'))

    def test_html_routes_load_and_user_content_is_not_inlined_as_html(self):
        Post.objects.create(author=self.ana, content='<script>alert(1)</script>')
        for path in ['/', '/explorar/', '/salvos/', '/configuracoes/', '/perfil/ana/', f'/post/{self.own.pk}/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, '<script>alert(1)</script>')

    def test_auth_pages_set_csrf_cookie(self):
        self.client.logout()
        for path in ['/entrar/', '/cadastro/']:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200)
            self.assertIn('csrftoken', result.cookies)

class AvatarTests(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = override_settings(MEDIA_ROOT=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)
        self.user = account('foto')
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_photo_only_patch_is_accepted_and_reencoded(self):
        result = self.client.patch('/api/me/', {'avatar': photo()}, format='multipart')
        self.assertEqual(result.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, 'Foto')
        self.assertTrue(self.user.check_password(PASSWORD))
        with Image.open(self.user.avatar.path) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertEqual(image.size, (512, 512))

    def test_replaced_and_removed_avatars_are_cleaned_up(self):
        self.client.patch('/api/me/', {'avatar': photo()}, format='multipart')
        self.user.refresh_from_db()
        original = Path(self.user.avatar.path)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.patch('/api/me/', {'avatar': photo('next.png')}, format='multipart')
        self.assertFalse(original.exists())
        self.user.refresh_from_db()
        second = Path(self.user.avatar.path)
        with self.captureOnCommitCallbacks(execute=True):
            result = self.client.patch('/api/me/', {'remove_avatar': True}, format='json')
        self.assertFalse(second.exists())
        self.assertFalse(result.data['avatar'])

    def test_non_image_and_svg_are_rejected(self):
        for filename, data in [('bad.png', b'not an image'), ('bad.svg', b'<svg><script/></svg>')]:
            result = self.client.patch('/api/me/', {'avatar': SimpleUploadedFile(filename, data)}, format='multipart')
            self.assertEqual(result.status_code, 400)

    def test_oversized_upload_is_rejected(self):
        image = photo()
        data = image.read() + b'0' * (2 * 1024 * 1024)
        result = self.client.patch('/api/me/', {'avatar': SimpleUploadedFile('large.png', data, content_type='image/png')}, format='multipart')
        self.assertEqual(result.status_code, 400)

    def test_conflicting_avatar_changes_do_not_save(self):
        result = self.client.patch('/api/me/', {'avatar': photo(), 'remove_avatar': 'true'}, format='multipart')
        self.assertEqual(result.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
