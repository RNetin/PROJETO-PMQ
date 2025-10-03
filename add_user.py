import sqlite3
from werkzeug.security import generate_password_hash
import db # Importa o nosso módulo db para inicializar a BD

DB_NAME = "analises.db"

def add_user():
    db.init_db() # Garante que a BD e as tabelas existem
    print("--- Adicionar Novo Utilizador ---")
    username = input("Digite o nome de utilizador: ").strip()
    password = input("Digite a senha: ").strip()
    is_admin_input = input("Tornar este utilizador um administrador? (s/n): ").strip().lower()
    
    is_admin = 1 if is_admin_input == 's' else 0

    if not username or not password:
        print("Nome de utilizador e senha não podem estar em branco.")
        return

    password_hash = generate_password_hash(password)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)", 
                       (username, password_hash, is_admin))
        conn.commit()
        print(f"Utilizador '{username}' adicionado com sucesso! Admin: {'Sim' if is_admin else 'Não'}")
    except sqlite3.IntegrityError:
        print(f"Erro: O nome de utilizador '{username}' já existe.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    add_user()