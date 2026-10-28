import sqlite3
from uuid import uuid4


def get_user(db: sqlite3.Connection, user_id: str):
    row = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_email(db: sqlite3.Connection, email: str):
    row = db.execute('SELECT * FROM users WHERE email = ?', (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


def list_users(db: sqlite3.Connection, limit: int = 100, offset: int = 0):
    return [dict(row) for row in db.execute(
        'SELECT * FROM users ORDER BY created_at, id LIMIT ? OFFSET ?', (limit, offset)
    ).fetchall()]


def create_user(db: sqlite3.Connection, *, email: str, name: str, surname: str,
                hashed_password: str, organization: str = '', role: str = 'user'):
    user_id = str(uuid4())
    with db:
        db.execute('''INSERT INTO users
            (id, email, name, surname, organization, hashed_password, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, email.strip().lower(), name, surname, organization, hashed_password, role))
    return get_user(db, user_id)


def update_user(db: sqlite3.Connection, user_id: str, **changes):
    allowed = {'email', 'name', 'surname', 'organization', 'hashed_password', 'role', 'is_active'}
    if changes.keys() - allowed:
        raise ValueError('Unsupported user fields')
    if 'email' in changes:
        changes['email'] = changes['email'].strip().lower()
    if changes:
        columns = ', '.join(f'{key} = ?' for key in changes)
        with db:
            db.execute(f'UPDATE users SET {columns} WHERE id = ?', (*changes.values(), user_id))
    return get_user(db, user_id)


def delete_user(db: sqlite3.Connection, user_id: str):
    with db:
        return db.execute('DELETE FROM users WHERE id = ?', (user_id,)).rowcount > 0
