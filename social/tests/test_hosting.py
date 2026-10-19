import json
import sys
import tempfile
from pathlib import Path
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import SimpleTestCase, override_settings
from dotenv import dotenv_values
from deploy.configure_pythonanywhere import configure

class HostingTests(SimpleTestCase):
    def test_config_normalizes_domain_but_preserves_username_in_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / 'Brunom89' / 'md-final-pio'
            project.mkdir(parents=True)
            result = configure(project, 'Brunom89')
            self.assertEqual(result['domain'], 'brunom89.pythonanywhere.com')
            self.assertIn('Brunom89', result['source_code'])
            values = dotenv_values(project / '.env')
            self.assertEqual(values['DJANGO_DEBUG'], '0')
            self.assertEqual(values['DJANGO_ALLOWED_HOSTS'], 'brunom89.pythonanywhere.com')
            self.assertEqual(values['DJANGO_CSRF_TRUSTED_ORIGINS'], 'https://brunom89.pythonanywhere.com')
            self.assertGreaterEqual(len(values['DJANGO_SECRET_KEY']), 64)
            self.assertNotIn(values['DJANGO_SECRET_KEY'], json.dumps(result))
            self.assertIn("'config.settings'", Path(result['wsgi_example']).read_text())

    def test_existing_private_environment_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            environment = Path(temporary) / '.env'
            environment.write_text('PRIVATE=keep\n')
            with self.assertRaises(ValueError):
                configure(temporary, 'student')
            self.assertEqual(environment.read_text(), 'PRIVATE=keep\n')

    def test_explicit_european_domain_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = configure(temporary, 'Student', 'Student.eu.pythonanywhere.com')
            self.assertEqual(result['domain'], 'student.eu.pythonanywhere.com')

    def test_invalid_domain_does_not_create_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                configure(temporary, 'student', 'attacker.example')
            self.assertFalse((Path(temporary) / '.env').exists())

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_production_static_css_and_javascript_are_served(self):
        for asset, text in [('css/style.css', 'app-shell'), ('js/app.js', 'renderRoute')]:
            response = self.client.get(staticfiles_storage.url(asset))
            self.assertEqual(response.status_code, 200)
            self.assertIn(text.encode(), b''.join(response.streaming_content))
