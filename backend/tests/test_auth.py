import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

# Isolate tests from the real database and signing secret before importing the app.
test_dir = tempfile.TemporaryDirectory()
os.environ['DATABASE_PATH'] = str(Path(test_dir.name) / 'test.sqlite3')
os.environ['JWT_SECRET_KEY'] = 'test-only-secret-with-at-least-32-bytes'
os.environ['ADMIN_EMAIL'] = ''
os.environ['ADMIN_PASSWORD'] = ''

import jwt
from fastapi.testclient import TestClient
from main import app
from src.config import SECRET_KEY, ALGORITHM
from src.database.connection import connect
from src.database import crud
from src.database.seed import seed_admin


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.__enter__()
        self.db = connect()
        with self.db:
            self.db.execute('DELETE FROM users')

    def tearDown(self):
        self.db.close()
        self.client.__exit__(None, None, None)

    def register(self, email='user@example.com'):
        return self.client.post('/api/signup', json={
            'email': email, 'password': 'test-password', 'name': 'Test', 'surname': 'User',
        })

    def login(self):
        response = self.client.post('/api/login', json={
            'email': 'USER@example.com', 'password': 'test-password',
        })
        self.assertEqual(response.status_code, 200)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def test_registration_and_crud(self):
        result = self.register()
        self.assertEqual(result.status_code, 201)
        self.assertNotIn('hashed_password', result.json()['user'])
        signup_headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
        self.assertEqual(self.client.get('/api/users/me', headers=signup_headers).status_code, 200)
        user = crud.get_user_by_email(self.db, 'user@example.com')
        self.assertNotEqual(user['hashed_password'], 'test-password')
        self.assertEqual(self.register('USER@example.com').status_code, 409)
        headers = self.login()
        self.assertEqual(self.client.get('/api/users/me', headers=headers).status_code, 200)
        result = self.client.patch('/api/users/me', headers=headers, json={'name': 'Updated'})
        self.assertEqual(result.json()['name'], 'Updated')
        self.assertEqual(self.client.delete('/api/users/me', headers=headers).status_code, 204)
        self.assertEqual(self.client.get('/api/users/me', headers=headers).status_code, 401)

    def test_invalid_credentials(self):
        self.register()
        for email in ['missing@example.com', 'user@example.com']:
            result = self.client.post('/api/login', json={'email': email, 'password': 'wrong'})
            self.assertEqual(result.status_code, 401)
        self.assertEqual(self.client.get('/api/users/me').status_code, 401)
        self.assertEqual(self.client.get('/api/users/me', headers={
            'Authorization': 'Bearer invalid',
        }).status_code, 401)
        user = crud.get_user_by_email(self.db, 'user@example.com')
        expired = jwt.encode({'sub': user['id'], 'iat': datetime.now(timezone.utc),
                              'exp': datetime.now(timezone.utc) - timedelta(seconds=1)},
                             SECRET_KEY, algorithm=ALGORITHM)
        self.assertEqual(self.client.get('/api/users/me', headers={
            'Authorization': 'Bearer ' + expired,
        }).status_code, 401)
        forged = jwt.encode({'sub': user['id'], 'iat': datetime.now(timezone.utc),
                             'exp': datetime.now(timezone.utc) + timedelta(minutes=5)},
                            'wrong-secret-with-at-least-32-bytes', algorithm=ALGORITHM)
        self.assertEqual(self.client.get('/api/users/me', headers={
            'Authorization': 'Bearer ' + forged,
        }).status_code, 401)

    def test_demo_admin_is_created_once_and_can_login(self):
        with patch.multiple('src.database.seed', ADMIN_EMAIL='admin@example.com',
                            ADMIN_PASSWORD='demo-password'):
            seed_admin(self.db)
            first = crud.get_user_by_email(self.db, 'admin@example.com')
            self.assertEqual(first['role'], 'admin')
            self.assertNotEqual(first['hashed_password'], 'demo-password')
            seed_admin(self.db)
            self.assertEqual(len(crud.list_users(self.db)), 1)
            self.assertEqual(crud.get_user(self.db, first['id'])['hashed_password'],
                             first['hashed_password'])
        result = self.client.post('/api/login', json={
            'email': 'admin@example.com', 'password': 'demo-password',
        })
        self.assertEqual(result.status_code, 200)
        headers = {'Authorization': 'Bearer ' + result.json()['access_token']}
        self.assertEqual(self.client.get('/api/users', headers=headers).status_code, 200)

    def test_demo_admin_does_not_promote_registered_users(self):
        self.register()
        with patch.multiple('src.database.seed', ADMIN_EMAIL='user@example.com',
                            ADMIN_PASSWORD='demo-password'):
            with self.assertRaises(RuntimeError):
                seed_admin(self.db)
        self.assertEqual(crud.get_user_by_email(self.db, 'user@example.com')['role'], 'user')

    def test_authorization_and_disabled_users(self):
        self.register()
        other = self.register('other@example.com').json()['user']
        headers = self.login()
        self.assertEqual(self.client.get('/api/users', headers=headers).status_code, 403)
        self.assertEqual(self.client.patch('/api/users/me', headers=headers,
                                          json={'role': 'admin'}).status_code, 422)
        user = crud.get_user_by_email(self.db, 'user@example.com')
        crud.update_user(self.db, user['id'], role='admin')
        self.assertEqual(self.client.get('/api/users', headers=headers).status_code, 200)
        crud.update_user(self.db, user['id'], role='user')
        self.assertEqual(self.client.get('/api/users', headers=headers).status_code, 403)
        crud.update_user(self.db, user['id'], role='admin')
        result = self.client.patch('/api/users/' + other['id'], headers=headers,
                                   json={'is_active': False})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['is_active'])
        self.assertEqual(self.client.delete('/api/users/' + other['id'], headers=headers).status_code, 204)
        crud.update_user(self.db, user['id'], is_active=False)
        self.assertEqual(self.client.get('/api/users/me', headers=headers).status_code, 401)
        self.assertEqual(self.client.post('/api/login', json={
            'email': user['email'], 'password': 'test-password',
        }).status_code, 401)


if __name__ == '__main__':
    unittest.main()
