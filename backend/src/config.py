import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / '.env')

DATABASE_PATH = Path(os.getenv('DATABASE_PATH', str(BACKEND_DIR / 'data' / 'app.sqlite3')))
SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '').strip().lower()
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')
ADMIN_NAME = os.getenv('ADMIN_NAME', 'Demo')
ADMIN_SURNAME = os.getenv('ADMIN_SURNAME', 'Admin')


def validate_settings():
    if len(SECRET_KEY.encode()) < 32:
        raise RuntimeError('Set JWT_SECRET_KEY in backend/.env to a random secret of at least 32 bytes.')
