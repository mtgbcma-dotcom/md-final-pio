"""Gera configuracao privada e WSGI sem alterar outras aplicacoes da conta."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sys

def configure(project, username, domain=None):
    project = Path(project).resolve()
    domain = (domain or f'{username}.pythonanywhere.com').lower()
    if not re.fullmatch(r'[a-z0-9.-]+\.pythonanywhere\.com', domain):
        raise ValueError('Use o dominio exibido na aba Web do PythonAnywhere.')
    environment = project / '.env'
    if environment.exists():
        raise ValueError('O arquivo .env ja existe e foi preservado. Revise a configuracao existente.')
    (project / 'data').mkdir(exist_ok=True)
    (project / 'media').mkdir(exist_ok=True)
    private = project / '.hosting'
    private.mkdir(exist_ok=True)
    values = {
        'DJANGO_DEBUG': '0', 'DJANGO_SECRET_KEY': secrets.token_hex(48),
        'DJANGO_ALLOWED_HOSTS': domain, 'DJANGO_CSRF_TRUSTED_ORIGINS': f'https://{domain}',
        'DJANGO_SECURE_SSL_REDIRECT': '1', 'SQLITE_DB_PATH': str(project / 'data' / 'db.sqlite3'),
        'MEDIA_ROOT': str(project / 'media'),
    }
    fd = os.open(environment, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        output.writelines(f'{key}={json.dumps(value)}\n' for key, value in values.items())
    wsgi = private / 'pythonanywhere_wsgi.py'
    wsgi.write_text(
        'import os\nimport sys\n\n'
        f'project_dir = {str(project)!r}\n'
        'if project_dir not in sys.path:\n    sys.path.insert(0, project_dir)\n\n'
        "os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'\n"
        'from django.core.wsgi import get_wsgi_application\n'
        'application = get_wsgi_application()\n', encoding='utf-8')
    return {'domain': domain, 'source_code': str(project), 'virtualenv': sys.prefix,
            'wsgi_example': str(wsgi), 'media_url': '/media/', 'media_directory': str(project / 'media')}

def main():
    parser = argparse.ArgumentParser(description='Prepara o Pio para PythonAnywhere.')
    parser.add_argument('--domain', help='Dominio exibido na aba Web, caso diferente do padrao.')
    options = parser.parse_args()
    if sys.prefix == sys.base_prefix:
        parser.error('Ative o ambiente virtual da hospedagem antes de continuar.')
    try:
        result = configure(Path(__file__).resolve().parent.parent, getpass.getuser(), options.domain)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    for key, value in result.items():
        print(f'{key}: {value}')
    print('Configuracao privada criada. Nenhuma chave foi exibida.')

if __name__ == '__main__':
    main()
