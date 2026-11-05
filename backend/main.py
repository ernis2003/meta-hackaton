from contextlib import asynccontextmanager, closing
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from src.config import validate_settings
from src.pcap_analysis import router as pcap_router
from src.analyses import router as analyses_router
from src.ai.routes import router as ai_router
from src.database import get_db, init_db
from src.database import crud
from src.database.connection import connect
from src.database.seed import seed_admin
from src.auth.authManager import (
    authenticate_user, create_access_token, get_current_user, get_password_hash, require_admin,
    verify_password,
)
from src.models.auth import (
    LoginRequest, SignupRequest, AdminUserUpdate, UserResponse, TokenResponse,
    ProfileUpdate, PasswordChange, AdminUserCreate, AdminUserResponse,
)


@asynccontextmanager
async def lifespan(app):
    validate_settings()
    init_db()
    with closing(connect()) as db:
        seed_admin(db)
    yield

app = FastAPI(title='Forensics API', version='1.0.0', lifespan=lifespan)
app.include_router(pcap_router)
app.include_router(analyses_router)
app.include_router(ai_router)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173'],
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])


@app.post('/api/signup', response_model=TokenResponse, status_code=201)
def signup(data: SignupRequest, db=Depends(get_db)):
    values = data.model_dump(exclude={'password'})
    try:
        user = crud.create_user(db, **values, hashed_password=get_password_hash(data.password))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='Email already registered') from None
    return {'access_token': create_access_token(user['id']), 'user': user}


@app.post('/api/login', response_model=TokenResponse)
def login(data: LoginRequest, db=Depends(get_db)):
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail='Incorrect email or password',
                            headers={'WWW-Authenticate': 'Bearer'})
    if user['role'] != data.role:
        raise HTTPException(status_code=403, detail='This account cannot sign in with the selected account type. Select the correct User or Admin tab.')
    return {'access_token': create_access_token(user['id']), 'user': user}


@app.get('/api/users/me', response_model=UserResponse)
def read_me(user=Depends(get_current_user)):
    return user


@app.patch('/api/users/me', response_model=UserResponse)
def update_me(data: ProfileUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    try:
        return crud.update_user(db, user['id'], **data.model_dump(exclude_unset=True))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='Email already registered') from None


@app.post('/api/users/me/password', status_code=204)
def change_my_password(data: PasswordChange, user=Depends(get_current_user), db=Depends(get_db)):
    if not verify_password(data.current_password.get_secret_value(), user['hashed_password']):
        raise HTTPException(status_code=400, detail='Current password is incorrect')
    hashed = get_password_hash(data.new_password.get_secret_value())
    with db:
        changed = db.execute('UPDATE users SET hashed_password=? WHERE id=? AND hashed_password=?',
                             (hashed, user['id'], user['hashed_password'])).rowcount
        if not changed:
            raise HTTPException(status_code=409, detail='Account changed during this request; try again')
    return Response(status_code=204)


@app.delete('/api/users/me', status_code=204)
def delete_me(user=Depends(get_current_user), db=Depends(get_db)):
    crud.delete_user(db, user['id'])
    return Response(status_code=204)


@app.get('/api/users', response_model=list[AdminUserResponse], dependencies=[Depends(require_admin)])
def list_users(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), db=Depends(get_db)):
    return crud.list_users(db, limit, offset)


@app.post('/api/users', response_model=UserResponse, status_code=201, dependencies=[Depends(require_admin)])
def create_managed_user(data: AdminUserCreate, db=Depends(get_db)):
    try:
        return crud.create_user(db, **data.model_dump(exclude={'password'}),
                                hashed_password=get_password_hash(data.password))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='Email already registered') from None


@app.get('/api/users/{user_id}', response_model=UserResponse, dependencies=[Depends(require_admin)])
def read_user(user_id: str, db=Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


def protect_admin_access(db, user, admin, changes=None):
    changes = changes or {}
    loses_access = changes.get('role', user['role']) != 'admin' or not changes.get('is_active', user['is_active'])
    deleting = changes == {'delete': True}
    if user['id'] == admin['id'] and (deleting or loses_access):
        raise HTTPException(409, 'You cannot delete, block or demote your own administrator account')
    if user['role'] == 'admin' and user['is_active'] and (deleting or loses_access):
        active_admins = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND is_active=1").fetchone()[0]
        if active_admins <= 1:
            raise HTTPException(409, 'The last active administrator must retain access')


@app.patch('/api/users/{user_id}', response_model=UserResponse)
def update_user(user_id: str, data: AdminUserUpdate, admin=Depends(require_admin), db=Depends(get_db)):
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            user = crud.get_user(db, user_id)
            if not user:
                raise HTTPException(status_code=404, detail='User not found')
            changes = data.model_dump(exclude_unset=True)
            protect_admin_access(db, user, admin, changes)
            return crud.update_user(db, user_id, **changes)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail='Email already registered') from None


@app.delete('/api/users/{user_id}', status_code=204)
def delete_user(user_id: str, admin=Depends(require_admin), db=Depends(get_db)):
    with db:
        db.execute('BEGIN IMMEDIATE')
        user = crud.get_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        protect_admin_access(db, user, admin, {'delete': True})
        crud.delete_user(db, user_id)
    return Response(status_code=204)


@app.get('/')
def root():
    return {'message': 'Forensics API'}
