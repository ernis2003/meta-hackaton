"""Use a private persistent signing key when no environment key was supplied."""
import os
from pathlib import Path
import secrets
import sys


def main():
    os.umask(0o077)
    if not os.getenv('JWT_SECRET_KEY'):
        directory = Path(os.getenv('DATABASE_PATH', '/data/app.sqlite3')).parent
        directory.mkdir(parents=True, exist_ok=True)
        secret_file = directory / '.jwt_secret'
        try:
            with secret_file.open('x', encoding='utf-8') as stream:
                stream.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass
        os.environ['JWT_SECRET_KEY'] = secret_file.read_text(encoding='utf-8').strip()
    if len(os.environ['JWT_SECRET_KEY'].encode()) < 32:
        raise RuntimeError('JWT_SECRET_KEY must contain at least 32 bytes; no key value was logged')
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == '__main__':
    main()
