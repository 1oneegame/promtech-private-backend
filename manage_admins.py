"""
Create admin user in database
Утилита для создания админ-пользователей в БД
"""

import sys
import os

# Добавляем путь к src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
from core import MongoDBConnection, AdminUsersRepository, AdminUser
import bcrypt


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_admin_in_db(username: str, password: str):
    """Создать админа в базе данных"""
    print(f"\n{'='*70}")
    print("CREATING ADMIN USER IN DATABASE")
    print(f"{'='*70}\n")
    
    # Подключение к БД
    print("Connecting to database...")
    db_connection = MongoDBConnection(local_mode=False)
    admin_repo = AdminUsersRepository(db_connection)
    
    # Проверка существования
    existing = admin_repo.get_user_by_username(username)
    if existing:
        print(f"❌ User '{username}' already exists!")
        db_connection.close()
        return False
    
    # Создание админа
    password_hash = get_password_hash(password)
    admin_user = AdminUser(
        username=username,
        password_hash=password_hash,
        role="admin",
        created_at=datetime.utcnow(),
        is_active=True
    )
    
    result = admin_repo.create_admin(admin_user)
    
    if result["success"]:
        print(f"✅ Admin user created successfully!")
        print(f"\nUsername: {username}")
        print(f"Password: {password}")
        print(f"Role: admin")
        print(f"\nYou can now login at: POST /auth/login")
        print(f"{'='*70}\n")
        db_connection.close()
        return True
    else:
        print(f"❌ Failed to create admin: {result.get('error')}")
        db_connection.close()
        return False


def list_admins():
    """Показать всех админов"""
    print(f"\n{'='*70}")
    print("ADMIN USERS LIST")
    print(f"{'='*70}\n")
    
    db_connection = MongoDBConnection(local_mode=False)
    admin_repo = AdminUsersRepository(db_connection)
    
    admins = admin_repo.get_all_admins()
    
    if not admins:
        print("No admin users found.")
    else:
        for i, admin in enumerate(admins, 1):
            print(f"{i}. {admin.username} (role: {admin.role}, active: {admin.is_active})")
    
    print(f"\n{'='*70}\n")
    db_connection.close()


def delete_admin(username: str):
    """Удалить админа"""
    print(f"\n{'='*70}")
    print(f"DELETING ADMIN USER: {username}")
    print(f"{'='*70}\n")
    
    db_connection = MongoDBConnection(local_mode=False)
    admin_repo = AdminUsersRepository(db_connection)
    
    success = admin_repo.delete_admin(username)
    
    if success:
        print(f"✅ Admin '{username}' deleted successfully!")
    else:
        print(f"❌ Failed to delete admin '{username}'")
    
    print(f"\n{'='*70}\n")
    db_connection.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  Create admin: python manage_admins.py create <username> <password>")
        print("  List admins:  python manage_admins.py list")
        print("  Delete admin: python manage_admins.py delete <username>")
        print("\nExamples:")
        print("  python manage_admins.py create john SecurePass123")
        print("  python manage_admins.py list")
        print("  python manage_admins.py delete john")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "create":
        if len(sys.argv) != 4:
            print("❌ Usage: python manage_admins.py create <username> <password>")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3]
        create_admin_in_db(username, password)
    
    elif command == "list":
        list_admins()
    
    elif command == "delete":
        if len(sys.argv) != 3:
            print("❌ Usage: python manage_admins.py delete <username>")
            sys.exit(1)
        username = sys.argv[2]
        delete_admin(username)
    
    else:
        print(f"❌ Unknown command: {command}")
        print("Available commands: create, list, delete")
        sys.exit(1)
