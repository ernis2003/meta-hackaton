from contextlib import asynccontextmanager, closing
import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from src.config import validate_settings
from src.database import get_db, init_db
from src.database import crud
from src.database.connection import connect
from src.database.seed import seed_admin
from src.auth.authManager import (
    authenticate_user, create_access_token, get_current_user, get_password_hash, require_admin,
)
from src.models.auth import (
    LoginRequest, SignupRequest, UserUpdate, AdminUserUpdate, UserResponse, TokenResponse,
)


@asynccontextmanager
async def lifespan(app):
    validate_settings()
    init_db()
    with closing(connect()) as db:
        seed_admin(db)
    yield

app = FastAPI(title='Forensics API', version='1.0.0', lifespan=lifespan)
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
def update_me(data: UserUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    return crud.update_user(db, user['id'], **data.model_dump(exclude_unset=True))


@app.delete('/api/users/me', status_code=204)
def delete_me(user=Depends(get_current_user), db=Depends(get_db)):
    crud.delete_user(db, user['id'])
    return Response(status_code=204)


@app.get('/api/users', response_model=list[UserResponse], dependencies=[Depends(require_admin)])
def list_users(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0), db=Depends(get_db)):
    return crud.list_users(db, limit, offset)


@app.get('/api/users/{user_id}', response_model=UserResponse, dependencies=[Depends(require_admin)])
def read_user(user_id: str, db=Depends(get_db)):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


@app.patch('/api/users/{user_id}', response_model=UserResponse, dependencies=[Depends(require_admin)])
def update_user(user_id: str, data: AdminUserUpdate, db=Depends(get_db)):
    user = crud.update_user(db, user_id, **data.model_dump(exclude_unset=True))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return user


@app.delete('/api/users/{user_id}', status_code=204, dependencies=[Depends(require_admin)])
def delete_user(user_id: str, db=Depends(get_db)):
    if not crud.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail='User not found')
    return Response(status_code=204)


@app.get('/')
def root():
    return {'message': 'Forensics API'}
