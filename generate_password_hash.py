# generate_password_hash.py - обновленная версия
from werkzeug.security import generate_password_hash
import sys
import secrets

def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python generate_password_hash.py <пароль>")
        print("  python generate_password_hash.py --generate-key")
        return
    
    if sys.argv[1] == '--generate-key':
        # Генерация секретного ключа для Flask
        key = secrets.token_hex(32)
        print(f"Сгенерированный SECRET_KEY:")
        print(key)
        return
    
    password = sys.argv[1]
    password_hash = generate_password_hash(password)
    print(f"Хеш для пароля '{password}':")
    print(password_hash)
    print("\nДобавьте в .env файл:")
    print(f"USER_PASSWORD_HASH={password_hash}  # для пользователя")
    print(f"ADMIN_PASSWORD_HASH={password_hash} # для администратора")

if __name__ == "__main__":
    main()