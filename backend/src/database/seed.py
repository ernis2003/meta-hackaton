"""Create the optional demo administrator once, without resetting existing accounts."""
from src.config import ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME, ADMIN_SURNAME
from src.auth.authManager import get_password_hash
from src.database import crud
from src.models.auth import SignupRequest


def seed_admin(db):
    if not ADMIN_EMAIL and not ADMIN_PASSWORD:
        return

    data = SignupRequest(email=ADMIN_EMAIL, password=ADMIN_PASSWORD,
                         name=ADMIN_NAME, surname=ADMIN_SURNAME)
    existing = crud.get_user_by_email(db, data.email)
    if existing:
        if existing['role'] != 'admin':
            raise RuntimeError('ADMIN_EMAIL already belongs to a regular user; use manage.py to grant access explicitly.')
        return
    crud.create_user(db, email=data.email, name=data.name, surname=data.surname,
                     hashed_password=get_password_hash(data.password), role='admin')
