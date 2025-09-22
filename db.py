import sqlite3
import json
from datetime import datetime

DB_NAME = "analises.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, timeout=15)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            site_url TEXT NOT NULL,
            site_nome TEXT,
            tipo_analise TEXT,
            respostas TEXT,
            last_modified TIMESTAMP
        )
    ''')
    try:
        cursor.execute('CREATE UNIQUE INDEX idx_user_url_tipo ON analises (username, site_url, tipo_analise)')
    except sqlite3.OperationalError:
        pass
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analise_id INTEGER,
            nome_arquivo TEXT,
            dados_pdf BLOB,
            data_geracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(analise_id) REFERENCES analises(id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def get_user_by_username(username):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def carregar_ou_criar_analise(username, site_url, site_nome, tipo_analise):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    cursor = conn.cursor()
    cursor.execute("SELECT id, respostas FROM analises WHERE username = ? AND site_url = ? AND tipo_analise = ?", 
                   (username, site_url, tipo_analise))
    row = cursor.fetchone()
    if row:
        analise_id, respostas_json = row
        respostas = json.loads(respostas_json) if respostas_json else {}
        cursor.execute("UPDATE analises SET site_nome = ?, last_modified = ? WHERE id = ?", (site_nome, datetime.now(), analise_id))
        conn.commit()
    else:
        cursor.execute("INSERT INTO analises (username, site_url, site_nome, tipo_analise, respostas, last_modified) VALUES (?, ?, ?, ?, ?, ?)", 
                       (username, site_url, site_nome, tipo_analise, json.dumps({}), datetime.now()))
        conn.commit()
        analise_id = cursor.lastrowid
        respostas = {}
    conn.close()
    return analise_id, respostas

def salvar_progresso(analise_id, respostas):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    cursor = conn.cursor()
    cursor.execute("UPDATE analises SET respostas = ?, last_modified = ? WHERE id = ?", (json.dumps(respostas), datetime.now(), analise_id))
    conn.commit()
    conn.close()

def listar_analises_por_usuario(username):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT id, site_url, site_nome, tipo_analise, last_modified, respostas FROM analises WHERE username = ? ORDER BY last_modified DESC", (username,))
    analises = cursor.fetchall()
    for analise in analises:
        if analise.get('respostas'):
            analise['respostas'] = json.loads(analise['respostas'])
        else:
            analise['respostas'] = {}
    conn.close()
    return analises

def obter_analise_por_id(analise_id, username):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM analises WHERE id = ? AND username = ?", (analise_id, username))
    analise = cursor.fetchone()
    if analise and analise.get('respostas'):
        analise['respostas'] = json.loads(analise['respostas'])
    else:
        if analise:
            analise['respostas'] = {}
    conn.close()
    return analise

def salvar_relatorio_db(analise_id, nome_arquivo, dados_pdf):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO relatorios (analise_id, nome_arquivo, dados_pdf) VALUES (?, ?, ?)",
                   (analise_id, nome_arquivo, dados_pdf))
    conn.commit()
    conn.close()

def get_latest_report(analise_id):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome_arquivo FROM relatorios WHERE analise_id = ? ORDER BY data_geracao DESC LIMIT 1", (analise_id,))
    report = cursor.fetchone()
    conn.close()
    return report

def get_report_data_by_id(relatorio_id):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT nome_arquivo, dados_pdf FROM relatorios WHERE id = ?", (relatorio_id,))
    report_data = cursor.fetchone()
    conn.close()
    return report_data

def delete_analise_by_id(analise_id, username):
    conn = sqlite3.connect(DB_NAME, timeout=15)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("DELETE FROM analises WHERE id = ? AND username = ?", (analise_id, username))
    conn.commit()
    changes = conn.total_changes
    conn.close()
    return changes > 0
