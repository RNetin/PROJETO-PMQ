import io
import os
from datetime import datetime
from pathlib import Path
from flask import (Flask, render_template, request, redirect, url_for, 
                   session, flash, jsonify, send_file, abort)
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import logic
import db

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-para-desenvolvimento-local')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
db.init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# As definições dos decoradores devem vir aqui, antes de serem usadas.
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Por favor, faça login para aceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Acesso negado. Esta área é apenas para administradores.', 'danger')
            return redirect(url_for('dashboard'))
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
            session['is_admin'] = user['is_admin']
            flash('Login bem-sucedido!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Utilizador ou senha inválidos.', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if not username or not password:
            flash('Nome de utilizador e senha são obrigatórios.', 'danger')
        else:
            password_hash = generate_password_hash(password)
            if db.add_new_user(username, password_hash):
                flash('Conta criada com sucesso! Por favor, faça login.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Este nome de utilizador já existe.', 'danger')
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    analises = db.listar_analises_por_usuario(session['username'])
    matriz_completa = logic.carregar_criterios()
    for analise in analises:
        criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
        score = 0
        selo = "Não iniciado"
        if criterios_para_analise and analise.get('respostas'):
            resultados = logic.calcular_indice_e_selo(analise['respostas'], criterios_para_analise)
            score = resultados['indice']
            selo = resultados['selo']
        analise['score'] = score
        analise['selo'] = selo
        if analise.get('last_modified'):
            dt_obj = datetime.strptime(analise['last_modified'].split('.')[0], '%Y-%m-%d %H:%M:%S')
            analise['last_modified_fmt'] = dt_obj.strftime('%d/%m/%Y às %H:%M')
        else:
            analise['last_modified_fmt'] = "N/A"
        analise['latest_report'] = db.get_latest_report(analise['id'])
    
    dados_grafico_selos = {
        "labels": [a['selo'] for a in analises if a['selo'] != "Não iniciado"],
        "data": [1 for a in analises if a['selo'] != "Não iniciado"]
    }
    selos_contagem = {}
    [selos_contagem.update({s: selos_contagem.get(s, 0) + 1}) for s in dados_grafico_selos['labels']]
    dados_grafico_selos = {"labels": list(selos_contagem.keys()), "data": list(selos_contagem.values())}

    scores_por_tipo = {
        "Prefeitura": [a['score'] for a in analises if a['tipo_analise'] == 'Prefeitura'],
        "Câmara": [a['score'] for a in analises if a['tipo_analise'] == 'Câmara']
    }
    media_prefeitura = sum(scores_por_tipo["Prefeitura"]) / len(scores_por_tipo["Prefeitura"]) if scores_por_tipo["Prefeitura"] else 0
    media_camara = sum(scores_por_tipo["Câmara"]) / len(scores_por_tipo["Câmara"]) if scores_por_tipo["Câmara"] else 0
    dados_grafico_medias = {"labels": ["Prefeitura", "Câmara"], "data": [media_prefeitura, media_camara]}
    
    return render_template('dashboard.html', analises=analises, dados_grafico_selos=dados_grafico_selos, dados_grafico_medias=dados_grafico_medias)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = db.list_all_users()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    db.delete_user_by_id(user_id)
    flash('Utilizador apagado com sucesso.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/reports')
@admin_required
def admin_reports():
    reports = db.list_all_reports()
    return render_template('admin_reports.html', reports=reports)

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

@app.route('/analise/<int:analise_id>', methods=['GET', 'POST'])
@login_required
def pagina_analise(analise_id):
    analise = db.obter_analise_por_id(analise_id, session['username'])
    if not analise:
        flash('Análise não encontrada.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        if 'imagem_justificativa' in request.files:
            file = request.files['imagem_justificativa']
            secao = request.form.get('secao')
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                unique_filename = f"analise_{analise_id}_{secao.lower()}_{datetime.now().strftime('%Y%m%d%H%M%S')}{os.path.splitext(filename)[1]}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file.save(filepath)
                db.update_image_path(analise_id, secao, unique_filename)
                flash('Imagem enviada com sucesso!', 'success')
                return redirect(url_for('pagina_analise', analise_id=analise_id))
            else:
                flash('Nenhum ficheiro selecionado ou tipo de ficheiro inválido (permitidos: png, jpg, jpeg, gif).', 'warning')
                return redirect(url_for('pagina_analise', analise_id=analise_id))

    matriz_completa = logic.carregar_criterios()
    criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
    return render_template('analise.html', analise=analise, matriz=criterios_para_analise)

@app.route('/analise/<int:analise_id>/gerar_relatorio', methods=['POST'])
@login_required
def gerar_relatorio_pdf(analise_id):
    analise = db.obter_analise_por_id(analise_id, session['username'])
    if not analise:
        flash('Análise não encontrada.', 'danger')
        return redirect(url_for('dashboard'))

    tipo_relatorio = request.form.get('tipo_relatorio', 'Relatório Completo')
    matriz_completa = logic.carregar_criterios()
    criterios_para_analise = matriz_completa.get(analise['tipo_analise'])
    
    matriz_a_usar = criterios_para_analise
    if tipo_relatorio == "Apenas Pontos a Melhorar":
        perguntas_filtradas = {}
        for secao, perguntas in criterios_para_analise.items():
            itens_nao_conformes = [item for item in perguntas if any(analise['respostas'].get(f"{secao}_{item['criterio']}_{sub}") == "Não Atende" for sub in item["subcriterios"])]
            if itens_nao_conformes:
                perguntas_filtradas[secao] = itens_nao_conformes
        matriz_a_usar = perguntas_filtradas

    resultados = logic.calcular_indice_e_selo(analise['respostas'], criterios_para_analise)
    scores_secao = {secao: logic.calcular_pontuacao_secao(analise['respostas'], perguntas, secao) for secao, perguntas in criterios_para_analise.items()}
    
    image_paths = {}
    if analise.get('receita_img_path'):
        path = Path(app.config['UPLOAD_FOLDER'], analise['receita_img_path']).resolve()
        image_paths['RECEITA'] = path.as_uri() if path.exists() else None
    else:
        image_paths['RECEITA'] = None
    
    if analise.get('despesa_img_path'):
        path = Path(app.config['UPLOAD_FOLDER'], analise['despesa_img_path']).resolve()
        image_paths['DESPESA'] = path.as_uri() if path.exists() else None
    else:
        image_paths['DESPESA'] = None

    html_string = render_template('relatorio_template.html', 
        site_nome=analise.get('site_nome', analise['site_url']),
        site_url=analise['site_url'],
        respostas=analise['respostas'],
        resultados=resultados,
        nome_usuario=session['username'],
        data_geracao=datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
        matriz_a_usar=matriz_a_usar,
        scores_secao=scores_secao,
        image_paths=image_paths
    )
    
    nome_arquivo, dados_pdf = logic.gerar_relatorio_com_weasyprint(html_string, analise['site_url'], base_url=request.url_root)
    
    if nome_arquivo and dados_pdf:
        db.salvar_relatorio_db(analise_id, nome_arquivo, dados_pdf)
        flash('Relatório gerado com sucesso!', 'success')
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
    # Cria a pasta de uploads se ela não existir
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=5000, debug=True)