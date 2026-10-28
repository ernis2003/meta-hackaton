"""Promote an existing account: python manage.py make-admin email@example.com."""
import argparse
from contextlib import closing

from src.database.connection import connect, init_db
from src.database.crud import get_user_by_email, update_user


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['make-admin'])
    parser.add_argument('email')
    args = parser.parse_args()
    init_db()
    with closing(connect()) as db:
        user = get_user_by_email(db, args.email)
        if not user:
            parser.error('Register the account before promoting it.')
        update_user(db, user['id'], role='admin')
        print('Administrator role granted.')


if __name__ == '__main__':
    main()
