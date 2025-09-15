import io
from datetime import datetime
from flask import (Flask, render_template, request, redirect, url_for, 
                   session, flash, jsonify, send_file, abort)
from functools import wraps
from werkzeug.security import check_password_hash

import logic
import db

app = Flask(__name__)
app.config['SECRET_KEY'] = 'uma-chave-secreta-muito-segura-trocar-depois'
db.init_db()

# ... (O resto do app.py, como login, dashboard, etc., continua o mesmo) ...
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = db.get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = user['username']
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    analises = db.listar_analises_por_usuario(session['username'])
    matriz_completa = logic.carregar_criterios()
    for analise in analises:
        criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
        if criterios_para_analise and analise.get('respostas'):
            resultados = logic.calcular_indice_e_selo(analise['respostas'], criterios_para_analise)
            analise['score'] = resultados['indice']
            analise['selo'] = resultados['selo']
        else:
            analise['score'] = 0
            analise['selo'] = "Não iniciado"
        if analise.get('last_modified'):
            dt_obj = datetime.strptime(analise['last_modified'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            analise['last_modified_fmt'] = dt_obj.strftime('%d/%m/%Y às %H:%M')
        else:
            analise['last_modified_fmt'] = "N/A"
        analise['latest_report'] = db.get_latest_report(analise['id'])
    return render_template('dashboard.html', analises=analises)

@app.route('/analise/nova', methods=['POST'])
@login_required
def nova_analise():
    site_url = request.form.get('site_url')
    site_nome = request.form.get('site_nome')
    tipo_analise = request.form.get('tipo_analise')
    if not all([site_url, site_nome, tipo_analise]):
        flash('Todos os campos são obrigatórios.', 'danger')
        return redirect(url_for('dashboard'))
    analise_id, _ = db.carregar_ou_criar_analise(session['username'], site_url, site_nome, tipo_analise)
    return redirect(url_for('pagina_analise', analise_id=analise_id))

@app.route('/analise/<int:analise_id>')
@login_required
def pagina_analise(analise_id):
    analise = db.obter_analise_por_id(analise_id, session['username'])
    if not analise:
        flash('Análise não encontrada.', 'danger')
        return redirect(url_for('dashboard'))
    matriz_completa = logic.carregar_criterios()
    criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
    return render_template('analise.html', analise=analise, matriz=criterios_para_analise)

# ===== ROTA DE GERAR RELATÓRIO ATUALIZADA =====
@app.route('/analise/<int:analise_id>/gerar_relatorio', methods=['POST']) # <-- A MUDANÇA ESTÁ AQUI
@login_required
def gerar_relatorio_pdf(analise_id):
    analise = db.obter_analise_por_id(analise_id, session['username'])
    if not analise:
        flash('Análise não encontrada.', 'danger')
        return redirect(url_for('dashboard'))

    # Pega a escolha do usuário do formulário. Padrão para 'Relatório Completo'
    tipo_relatorio = request.form.get('tipo_relatorio', 'Relatório Completo')

    matriz_completa = logic.carregar_criterios()
    criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
    
    matriz_a_usar = criterios_para_analise
    if tipo_relatorio == "Apenas Pontos a Melhorar":
        perguntas_filtradas = {}
        for secao, perguntas in criterios_para_analise.items():
            itens_nao_conformes = [
                item for item in perguntas 
                if any(analise['respostas'].get(f"{secao}_{item['criterio']}_{sub}") == "Não Atende" for sub in item["subcriterios"])
            ]
            if itens_nao_conformes:
                perguntas_filtradas[secao] = itens_nao_conformes
        matriz_a_usar = perguntas_filtradas

    resultados = logic.calcular_indice_e_selo(analise['respostas'], criterios_para_analise)
    scores_secao = {
        secao: logic.calcular_pontuacao_secao(analise['respostas'], perguntas, secao)
        for secao, perguntas in criterios_para_analise.items()
    }
    
    html_string = render_template('relatorio_template.html', 
        site_nome=analise.get('site_nome', analise['site_url']),
        site_url=analise['site_url'],
        respostas=analise['respostas'],
        resultados=resultados,
        nome_usuario=session['username'],
        data_geracao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        matriz_a_usar=matriz_a_usar,
        scores_secao=scores_secao
    )
    
    nome_arquivo, dados_pdf = logic.gerar_relatorio_com_weasyprint(html_string, analise['site_url'], base_url=request.url_root)

    if nome_arquivo and dados_pdf:
        db.salvar_relatorio_db(analise_id, nome_arquivo, dados_pdf)
        flash('Relatório gerado com sucesso! Você pode baixá-lo no dashboard.', 'success')
        return redirect(url_for('dashboard'))
    else:
        flash('Ocorreu um erro ao gerar o relatório.', 'danger')
        return redirect(url_for('pagina_analise', analise_id=analise_id))

@app.route('/relatorio/<int:relatorio_id>/download')
@login_required
def download_relatorio(relatorio_id):
    report_data = db.get_report_data_by_id(relatorio_id)
    if not report_data:
        return abort(404)
    return send_file(io.BytesIO(report_data['dados_pdf']), mimetype='application/pdf', as_attachment=True, download_name=report_data['nome_arquivo'])

@app.route('/analise/<int:analise_id>/apagar', methods=['POST'])
@login_required
def delete_analise(analise_id):
    success = db.delete_analise_by_id(analise_id, session['username'])
    if success:
        flash('Análise apagada com sucesso.', 'success')
    else:
        flash('Não foi possível apagar a análise.', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/api/analise/<int:analise_id>/salvar', methods=['POST'])
@login_required
def salvar_progresso(analise_id):
    respostas = request.json
    try:
        db.salvar_progresso(analise_id, respostas)
        return jsonify({'status': 'sucesso', 'mensagem': 'Progresso salvo!'})
    except Exception as e:
        return jsonify({'status': 'erro', 'mensagem': 'Falha ao salvar.'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)