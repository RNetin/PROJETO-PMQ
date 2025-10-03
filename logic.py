import json
import os
from datetime import datetime
from functools import lru_cache
from urllib.parse import urlparse
from weasyprint import HTML



@lru_cache(maxsize=4)
def carregar_criterios(caminho_arquivo="data/criterios_analise_site.json"):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"ERRO: O arquivo de dados '{caminho_arquivo}' não foi encontrado.")
    except json.JSONDecodeError:
        raise ValueError(f"ERRO: O arquivo '{caminho_arquivo}' contém um erro de formatação JSON.")

def criar_pastas_necessarias():
    os.makedirs("relatorios", exist_ok=True)

def calcular_indice_e_selo(respostas, criterios_analise):
    pesos = {"ESSENCIAL": 2.0, "OBRIGATÓRIA": 1.5, "RECOMENDADA": 1.0}
    total_pontos_possiveis, pontos_obtidos = 0, 0
    total_essenciais, essenciais_atendidos = 0, 0
    for secao, perguntas in criterios_analise.items():
        for item in perguntas:
            classificacao = item.get("classificacao", "RECOMENDADA").upper()
            peso = pesos.get(classificacao, 1.0)
            total_pontos_possiveis += peso
            chave_base = f"{secao}_{item['criterio']}"
            status_geral_atende = not any(
                respostas.get(f"{chave_base}_{sub}") == "Não Atende" for sub in item["subcriterios"]
            )
            if status_geral_atende:
                pontos_obtidos += peso
            if classificacao == "ESSENCIAL":
                total_essenciais += 1
                if status_geral_atende:
                    essenciais_atendidos += 1
    percentual_essenciais = (essenciais_atendidos / total_essenciais * 100) if total_essenciais > 0 else 100
    indice = (pontos_obtidos / total_pontos_possiveis * 100) if total_pontos_possiveis > 0 else 0
    selo = "Inexistente"
    if indice > 0:
        if percentual_essenciais == 100:
            if indice >= 95: selo = "💎 Diamante"
            elif indice >= 85: selo = "🥇 Ouro"
            elif indice >= 75: selo = "🥈 Prata"
            else: selo = "Elevado (não elegível para selo)"
        else:
            if indice >= 75: selo = "Elevado"
            elif indice >= 50: selo = "Intermediário"
            elif indice >= 30: selo = "Básico"
            else: selo = "Inicial"
    return {"indice": indice, "selo": selo, "percentual_essenciais": percentual_essenciais}

def calcular_pontuacao_secao(respostas, perguntas_secao, nome_secao):
    pesos = {"ESSENCIAL": 2.0, "OBRIGATÓRIA": 1.5, "RECOMENDADA": 1.0}
    total_pontos_possiveis, pontos_obtidos = 0, 0
    for item in perguntas_secao:
        classificacao = item.get("classificacao", "RECOMENDADA").upper()
        peso = pesos.get(classificacao, 1.0)
        total_pontos_possiveis += peso
        chave_base = f"{nome_secao}_{item['criterio']}"
        if not any(respostas.get(f"{chave_base}_{sub}") == "Não Atende" for sub in item["subcriterios"]):
            pontos_obtidos += peso
    return (pontos_obtidos / total_pontos_possiveis * 100) if total_pontos_possiveis > 0 else 100

def gerar_relatorio_com_weasyprint(html_string, site_url, base_url):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parsed_url = urlparse(site_url)
    netloc = parsed_url.netloc
    path = parsed_url.path
    safe_filename_part = (netloc + path).replace('/', '_').replace('?', '_').replace('=', '-').replace('&', '_').replace(':', '_')
    if safe_filename_part.endswith(('_', '.')):
        safe_filename_part = safe_filename_part[:-1]
    nome_base = f"Relatorio_{safe_filename_part}_{timestamp}"
    nome_arquivo_pdf = f"{nome_base}.pdf"

  
    pdf_data = HTML(string=html_string, base_url=base_url).write_pdf()

    return nome_arquivo_pdf, pdf_data