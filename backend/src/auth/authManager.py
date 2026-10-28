from datetime import datetime, timedelta, timezone
import secrets

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from src.config import ALGORITHM, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, validate_settings
from src.database import get_db
from src.database.crud import get_user, get_user_by_email

password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)


def verify_password(plain_password: str, hashed_password: str):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return password_hash.hash(password)


def authenticate_user(db, email: str, password: str):
    user = get_user_by_email(db, email)
    valid = verify_password(password, user['hashed_password'] if user else DUMMY_HASH)
    if not user or not valid or not user['is_active']:
        return None
    return user


def create_access_token(user_id: str):
    validate_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': user_id, 'iat': now,
                       'exp': now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)},
                      SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db=Depends(get_db)):
    error = HTTPException(status_code=401, detail='Invalid or expired credentials',
                          headers={'WWW-Authenticate': 'Bearer'})
    if credentials is None:
        raise error
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM],
                             options={'require': ['sub', 'exp', 'iat']})
        user_id = payload['sub']
        if not isinstance(user_id, str):
            raise error
    except InvalidTokenError:
        raise error from None
    user = get_user(db, user_id)
    if not user or not user['is_active']:
        raise error
    return user


def require_admin(user=Depends(get_current_user)):
    if user['role'] != 'admin':
        raise HTTPException(status_code=403, detail='Administrator access required')
    return user
