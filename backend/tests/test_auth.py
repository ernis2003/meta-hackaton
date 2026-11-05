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
            'email': 'admin@example.com', 'password': 'demo-password', 'role': 'admin',
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

    def test_login_requires_matching_account_type(self):
        self.register()
        for role, expected in [('user', 200), ('admin', 403)]:
            result = self.client.post('/api/login', json={
                'email': 'user@example.com', 'password': 'test-password', 'role': role,
            })
            self.assertEqual(result.status_code, expected)
            if expected != 200:
                self.assertNotIn('access_token', result.json())

        user = crud.get_user_by_email(self.db, 'user@example.com')
        crud.update_user(self.db, user['id'], role='admin')
        for role, expected in [('user', 403), ('admin', 200)]:
            result = self.client.post('/api/login', json={
                'email': user['email'], 'password': 'test-password', 'role': role,
            })
            self.assertEqual(result.status_code, expected)
            if expected != 200:
                self.assertNotIn('access_token', result.json())
        result = self.client.post('/api/login', json={
            'email': user['email'], 'password': 'test-password',
        })
        self.assertEqual(result.status_code, 403)
        self.assertNotIn('access_token', result.json())

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


    def test_profile_update_and_read_only_fields_for_both_roles(self):
        self.register('taken@example.com')
        for role in ('user', 'admin'):
            with self.subTest(role=role):
                created = self.register(role + '@example.com').json()
                user_id = created['user']['id']
                crud.update_user(self.db, user_id, role=role)
                headers = {'Authorization': 'Bearer ' + created['access_token']}
                response = self.client.patch('/api/users/me', headers=headers, json={
                    'name': '  Updated  ', 'surname': '  Analyst  ',
                    'organization': '  SOC Team  ', 'email': ' UPDATED-' + role + '@EXAMPLE.COM ',
                })
                self.assertEqual(response.status_code, 200, response.text)
                profile = response.json()
                self.assertEqual(profile['name'], 'Updated')
                self.assertEqual(profile['surname'], 'Analyst')
                self.assertEqual(profile['organization'], 'SOC Team')
                self.assertEqual(profile['email'], 'updated-' + role + '@example.com')
                self.assertEqual(profile['role'], role)
                self.assertNotIn('hashed_password', profile)
                self.assertEqual(self.client.get('/api/users/me', headers=headers).json(), profile)
                for field, value in [('role', 'admin'), ('is_active', False),
                                     ('created_at', '2000-01-01'), ('hashed_password', 'not-allowed'),
                                     ('id', 'other-user')]:
                    response = self.client.patch('/api/users/me', headers=headers, json={field: value})
                    self.assertEqual(response.status_code, 422, field)
                conflict = self.client.patch('/api/users/me', headers=headers,
                                             json={'email': 'TAKEN@example.com'})
                self.assertEqual(conflict.status_code, 409)
                self.assertEqual(crud.get_user(self.db, user_id)['email'], profile['email'])

    def test_profile_rejects_invalid_values_and_requires_authorization(self):
        created = self.register().json()
        headers = {'Authorization': 'Bearer ' + created['access_token']}
        for invalid in ({'name': '   '}, {'surname': ''}, {'name': None}, {'organization': None},
                        {'email': None}, {'email': 'invalid'}, {'email': 'two@@example.com'},
                        {'organization': 'x' * 201}):
            response = self.client.patch('/api/users/me', headers=headers, json=invalid)
            self.assertEqual(response.status_code, 422, str(invalid.keys()))
        self.assertEqual(self.client.patch('/api/users/me', json={'name': 'No access'}).status_code, 401)
        self.assertEqual(crud.get_user(self.db, created['user']['id'])['name'], 'Test')

    def test_password_change_verifies_current_password_and_both_roles_can_login(self):
        for role in ('user', 'admin'):
            with self.subTest(role=role):
                email = role + '@example.com'
                created = self.register(email).json()
                user_id = created['user']['id']
                crud.update_user(self.db, user_id, role=role)
                old_hash = crud.get_user(self.db, user_id)['hashed_password']
                headers = {'Authorization': 'Bearer ' + created['access_token']}
                payload = dict(current_password='wrong', new_password='New-SecurePass2026!',
                               confirm_password='New-SecurePass2026!')
                response = self.client.post('/api/users/me/password', headers=headers, json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(crud.get_user(self.db, user_id)['hashed_password'], old_hash)
                payload['current_password'] = 'test-password'
                response = self.client.post('/api/users/me/password', headers=headers, json=payload)
                self.assertEqual(response.status_code, 204, response.text)
                self.assertEqual(response.content, b'')
                new_hash = crud.get_user(self.db, user_id)['hashed_password']
                self.assertNotEqual(new_hash, old_hash)
                self.assertNotEqual(new_hash, payload['new_password'])
                for password, expected in [('test-password', 401), (payload['new_password'], 200)]:
                    login = self.client.post('/api/login', json=dict(email=email, password=password, role=role))
                    self.assertEqual(login.status_code, expected)
                    self.assertNotIn('hashed_password', login.text)

    def test_password_validation_authentication_and_disabled_account(self):
        created = self.register().json()
        headers = {'Authorization': 'Bearer ' + created['access_token']}
        valid = dict(current_password='test-password', new_password='New-SecurePass2026!',
                     confirm_password='New-SecurePass2026!')
        for change in [dict(confirm_password='Other-SecurePass2026!'),
                       dict(new_password='weak', confirm_password='weak'),
                       dict(new_password='longbutweakpassword', confirm_password='longbutweakpassword'),
                       dict(new_password='test-password', confirm_password='test-password'),
                       dict(role='admin'), dict(current_password='')]:
            response = self.client.post('/api/users/me/password', headers=headers, json={**valid, **change})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.post('/api/users/me/password', json=valid).status_code, 401)
        crud.update_user(self.db, created['user']['id'], is_active=False)
        self.assertEqual(self.client.post('/api/users/me/password', headers=headers, json=valid).status_code, 401)
        self.assertEqual(self.client.patch('/api/users/me', headers=headers, json={'name': 'Blocked'}).status_code, 401)


    def admin_headers(self):
        created = self.register('admin@example.com').json()
        crud.update_user(self.db, created['user']['id'], role='admin')
        return {'Authorization': 'Bearer ' + created['access_token']}, created['user']['id']

    def test_admin_creates_accounts_and_rejects_duplicate_or_invalid_data(self):
        headers, _ = self.admin_headers()
        payload = dict(email=' NEW@example.com ', password='Initial-Password2026!',
                       name='  New  ', surname='  Analyst  ', organization='  SOC  ',
                       role='admin', is_active=False)
        self.assertEqual(self.client.post('/api/users', json=payload).status_code, 401)
        regular = self.register('regular@example.com').json()
        regular_headers = {'Authorization': 'Bearer ' + regular['access_token']}
        self.assertEqual(self.client.post('/api/users', headers=regular_headers, json=payload).status_code, 403)
        response = self.client.post('/api/users', headers=headers, json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        self.assertEqual((created['email'], created['name'], created['surname'], created['organization']),
                         ('new@example.com', 'New', 'Analyst', 'SOC'))
        self.assertEqual(created['role'], 'admin')
        self.assertFalse(created['is_active'])
        self.assertNotIn('password', response.text)
        self.assertNotEqual(crud.get_user(self.db, created['id'])['hashed_password'], payload['password'])
        self.assertEqual(self.client.post('/api/users', headers=headers, json=payload).status_code, 409)
        for invalid in [dict(email='bad'), dict(name='   '), dict(password='short'),
                        dict(role='superadmin'), dict(hashed_password='injected')]:
            self.assertEqual(self.client.post('/api/users', headers=headers,
                                              json={**payload, **invalid}).status_code, 422)

    def test_admin_list_has_real_analysis_counts_and_pagination_without_hashes(self):
        headers, _ = self.admin_headers()
        user = self.register().json()['user']
        with self.db:
            for i in range(2):
                self.db.execute("INSERT INTO analyses(id,user_id,filename,status) VALUES(?,?,?,'completed')",
                                ('count-test-' + str(i), user['id'], 'count-test.pcap'))
        response = self.client.get('/api/users', headers=headers)
        self.assertEqual(response.status_code, 200)
        listed = {item['id']: item for item in response.json()}
        self.assertEqual(listed[user['id']]['analysis_count'], 2)
        self.assertNotIn('hashed_password', response.text)
        first = self.client.get('/api/users?limit=1&offset=0', headers=headers).json()
        second = self.client.get('/api/users?limit=1&offset=1', headers=headers).json()
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertNotEqual(first[0]['id'], second[0]['id'])

    def test_admin_update_block_unblock_and_delete_preserve_authorization(self):
        headers, _ = self.admin_headers()
        created = self.register().json()
        user_id = created['user']['id']
        user_headers = {'Authorization': 'Bearer ' + created['access_token']}
        response = self.client.patch('/api/users/' + user_id, headers=headers,
                                     json=dict(email='updated@example.com', name='Edited', role='admin'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['email'], 'updated@example.com')
        self.assertEqual(response.json()['role'], 'admin')
        self.assertEqual(self.client.patch('/api/users/' + user_id, headers=headers,
                                          json={'email': 'admin@example.com'}).status_code, 409)
        self.assertEqual(self.client.patch('/api/users/' + user_id, headers=headers,
                                          json={'is_active': False}).status_code, 200)
        self.assertEqual(self.client.get('/api/users/me', headers=user_headers).status_code, 401)
        self.assertEqual(self.client.patch('/api/users/' + user_id, headers=headers,
                                          json={'is_active': True, 'role': 'user'}).status_code, 200)
        self.assertEqual(self.client.get('/api/users/me', headers=user_headers).status_code, 200)
        self.assertEqual(self.client.delete('/api/users/' + user_id, headers=user_headers).status_code, 403)
        self.assertEqual(self.client.delete('/api/users/' + user_id, headers=headers).status_code, 204)
        self.assertEqual(self.client.get('/api/users/me', headers=user_headers).status_code, 401)

    def test_admin_cannot_block_demote_or_delete_own_account(self):
        headers, admin_id = self.admin_headers()
        for changes in ({'role': 'user'}, {'is_active': False}):
            response = self.client.patch('/api/users/' + admin_id, headers=headers, json=changes)
            self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.delete('/api/users/' + admin_id, headers=headers).status_code, 409)
        admin = crud.get_user(self.db, admin_id)
        self.assertEqual(admin['role'], 'admin')
        self.assertTrue(admin['is_active'])
        self.assertEqual(self.client.patch('/api/users/' + admin_id, headers=headers,
                                          json={'name': 'Updated Admin'}).status_code, 200)


if __name__ == '__main__':
    unittest.main()
