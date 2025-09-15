import sqlite3
from werkzeug.security import generate_password_hash

DB_NAME = "analises.db"

def add_user():
    print("--- Adicionar Novo Usuário ---")
    username = input("Digite o nome de usuário: ").strip()
    password = input("Digite a senha: ").strip()
    
    if not username or not password:
        print("Nome de usuário e senha não podem estar em branco.")
        return

    # Gera o hash seguro da senha
    password_hash = generate_password_hash(password)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        print(f"Usuário '{username}' adicionado com sucesso!")
    except sqlite3.IntegrityError:
        print(f"Erro: O nome de usuário '{username}' já existe.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_user()