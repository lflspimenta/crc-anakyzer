
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import re
import json
from datetime import datetime
import pandas as pd
import pdfplumber
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = 'uploads'

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class CRCAnalyzer:
    def __init__(self):
        self.creditos = []
        self.resumo = {}
        self.metricas = {}
        self.recomendacoes = []

    def extrair_dados_pdf(self, pdf_path):
        dados_extraidos = {
            'titular': '',
            'data_consulta': '',
            'creditos': [],
            'resumo': {}
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                primeira_pagina = pdf.pages[0]
                texto_primeira = primeira_pagina.extract_text() or ""
                dados_extraidos['titular'] = self._extrair_titular(texto_primeira)
                dados_extraidos['data_consulta'] = self._extrair_data_consulta(texto_primeira)

                for i, page in enumerate(pdf.pages):
                    texto = page.extract_text() or ""
                    if 'Informacao comunicada' in texto or 'Informacao' in texto:
                        credito = self._extrair_credito_pagina(texto)
                        if credito and credito['entidade']:
                            dados_extraidos['creditos'].append(credito)

                if not dados_extraidos['creditos']:
                    for i, page in enumerate(pdf.pages):
                        texto = page.extract_text() or ""
                        credito = self._extrair_credito_texto_livre(texto)
                        if credito and credito['entidade']:
                            dados_extraidos['creditos'].append(credito)

        except Exception as e:
            print(f"Erro na extracao: {e}")

        return dados_extraidos

    def _extrair_titular(self, texto):
        match = re.search(r'Nome[:\s]+([A-Z][A-Z\s]+[A-Z])', texto)
        if match:
            return match.group(1).strip()
        match = re.search(r'Nome[:\s]+([\w\s]+)', texto)
        if match:
            return match.group(1).strip()
        return "Titular nao identificado"

    def _extrair_data_consulta(self, texto):
        match = re.search(r'Data de Emiss[ãa]o[:\s]+(\d{2}-\d{2}-\d{4})', texto)
        if match:
            data = match.group(1)
            return data.replace('-', '/')
        match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
        if match:
            return match.group(1)
        return datetime.now().strftime("%d/%m/%Y")

    def _extrair_credito_pagina(self, texto):
        credito = {
            'entidade': '', 'produto': '', 'tipo_negociacao': '',
            'data_inicio': '', 'data_fim': '', 'montante_inicial': 0.0,
            'montante_divida': 0.0, 'montante_vencido': 0.0,
            'montante_abatido': 0.0, 'prestacao_mensal': 0.0,
            'taxa_juro': 0.0, 'prazo_total': 0, 'prazo_restante': 0,
            'situacao': 'Regular', 'garantias': [], 'fiadores': []
        }

        # Entidade - procurar padrao especifico do CRC
        linhas = texto.split('\n')
        for linha in linhas:
            if 'Informacao comunicada pela instituicao' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    credito['entidade'] = partes[1].strip()
            elif 'Produto financeiro' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    credito['produto'] = partes[1].strip()
            elif 'Tipo de negociacao' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    credito['tipo_negociacao'] = partes[1].strip()
            elif 'Inicio:' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    data = partes[1].strip()
                    if len(data) == 10 and data[4] == '-':
                        credito['data_inicio'] = f"{data[8:10]}/{data[5:7]}/{data[0:4]}"
            elif 'Fim:' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    data = partes[1].strip()
                    if len(data) == 10 and data[4] == '-':
                        credito['data_fim'] = f"{data[8:10]}/{data[5:7]}/{data[0:4]}"
            elif 'Total em divida' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    credito['montante_divida'] = self._parse_montante(val_str)
            elif 'em incumprimento' in linha.lower():
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    val = self._parse_montante(val_str)
                    if val > 0:
                        credito['situacao'] = 'Incumprimento'
            elif 'Vencido' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    credito['montante_vencido'] = self._parse_montante(val_str)
            elif 'Abatido ao ativo' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    credito['montante_abatido'] = self._parse_montante(val_str)
            elif 'Prestacao' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    credito['prestacao_mensal'] = self._parse_montante(val_str)
            elif 'Potencial' in linha:
                partes = linha.split(':')
                if len(partes) > 1:
                    val_str = partes[1].replace('EUR', '').replace('€', '').strip()
                    credito['montante_inicial'] = self._parse_montante(val_str)
            elif 'Em litigio judicial' in linha or 'Em liti' in linha:
                credito['situacao'] = 'Litigio Judicial'

        return credito

    def _extrair_credito_texto_livre(self, texto):
        credito = {
            'entidade': '', 'produto': '', 'tipo_negociacao': '',
            'data_inicio': '', 'data_fim': '', 'montante_inicial': 0.0,
            'montante_divida': 0.0, 'montante_vencido': 0.0,
            'montante_abatido': 0.0, 'prestacao_mensal': 0.0,
            'taxa_juro': 0.0, 'prazo_total': 0, 'prazo_restante': 0,
            'situacao': 'Regular', 'garantias': [], 'fiadores': []
        }

        linhas = texto.split('\n')
        for i, linha in enumerate(linhas):
            if 'BANCO' in linha.upper() and 'instituicao' in linha.lower():
                match = re.search(r'BANCO\s+[^\n]+', linha)
                if match:
                    credito['entidade'] = match.group(0).strip()

            if 'Produto financeiro' in linha:
                match = re.search(r'Produto financeiro[:\s]+(.+)', linha)
                if match:
                    credito['produto'] = match.group(1).strip()

            valores = re.findall(r'([\d\.,]+)\s*€', linha)
            if valores:
                if 'divida' in linha.lower():
                    credito['montante_divida'] = self._parse_montante(valores[0])
                elif 'prestacao' in linha.lower():
                    credito['prestacao_mensal'] = self._parse_montante(valores[0])
                elif 'vencido' in linha.lower():
                    credito['montante_vencido'] = self._parse_montante(valores[0])

        return credito

    def _parse_montante(self, valor_str):
        if not valor_str:
            return 0.0
        limpo = re.sub(r'[^\d,\.]', '', str(valor_str))
        limpo = limpo.replace('.', '').replace(',', '.')
        try:
            return float(limpo) if limpo else 0.0
        except:
            return 0.0

    def calcular_metricas(self, creditos, rendimento_mensal=2000):
        if not creditos:
            return {}
        total_divida = sum(c['montante_divida'] for c in creditos)
        total_vencido = sum(c['montante_vencido'] for c in creditos)
        total_abatido = sum(c['montante_abatido'] for c in creditos)
        total_prestacoes = sum(c['prestacao_mensal'] for c in creditos if c['situacao'] != 'Liquidado')
        n_creditos = len([c for c in creditos if c['situacao'] != 'Liquidado'])
        n_incumprimentos = len([c for c in creditos if c['situacao'] == 'Incumprimento'])
        taxa_esforco = (total_prestacoes / rendimento_mensal * 100) if rendimento_mensal > 0 else 0
        endividamento_anual = total_divida / (rendimento_mensal * 12) if rendimento_mensal > 0 else 0
        risco_incumprimento = (total_vencido / total_divida * 100) if total_divida > 0 else 0

        score = 100
        score -= min(taxa_esforco * 1.5, 40)
        score -= min(endividamento_anual * 10, 25)
        score -= min(n_incumprimentos * 15, 30)
        score -= min(risco_incumprimento * 2, 20)
        score = max(0, min(100, score))

        if score >= 80:
            classificacao, cor = 'Excelente', '#28a745'
        elif score >= 60:
            classificacao, cor = 'Bom', '#6c757d'
        elif score >= 40:
            classificacao, cor = 'Atencao', '#ffc107'
        elif score >= 20:
            classificacao, cor = 'Risco', '#fd7e14'
        else:
            classificacao, cor = 'Critico', '#dc3545'

        return {
            'total_divida': total_divida, 'total_vencido': total_vencido,
            'total_abatido': total_abatido, 'total_prestacoes': total_prestacoes,
            'n_creditos_ativos': n_creditos, 'n_incumprimentos': n_incumprimentos,
            'taxa_esforco': round(taxa_esforco, 2),
            'endividamento_anual': round(endividamento_anual, 2),
            'risco_incumprimento': round(risco_incumprimento, 2),
            'score': round(score, 1), 'classificacao': classificacao,
            'cor_classificacao': cor, 'rendimento_mensal': rendimento_mensal
        }

    def gerar_recomendacoes(self, creditos, metricas):
        recomendacoes = []
        if metricas['taxa_esforco'] > 40:
            recomendacoes.append({
                'tipo': 'urgente', 'titulo': 'Taxa de Esforco Critica',
                'descricao': f"A taxa de esforco esta em {metricas['taxa_esforco']}%, muito acima do limite recomendado de 30-35%.",
                'acao': 'Consolidar Creditos', 'impacto': 'Reduzir prestacoes mensais em 20-40%'
            })
        elif metricas['taxa_esforco'] > 30:
            recomendacoes.append({
                'tipo': 'alerta', 'titulo': 'Taxa de Esforco Elevada',
                'descricao': f"Taxa de esforco de {metricas['taxa_esforco']}% esta acima do recomendado.",
                'acao': 'Renegociar Prazos', 'impacto': 'Reduzir prestacoes em 10-20%'
            })
        if metricas['n_incumprimentos'] > 0:
            recomendacoes.append({
                'tipo': 'urgente', 'titulo': f"{metricas['n_incumprimentos']} Credito(s) em Incumprimento",
                'descricao': f"Existem {metricas['n_incumprimentos']} creditos em incumprimento com {metricas['total_vencido']:,.2f}EUR vencidos.",
                'acao': 'Regularizar Dividas', 'impacto': 'Evitar registo negativo no Banco de Portugal'
            })
        if metricas['endividamento_anual'] > 3:
            recomendacoes.append({
                'tipo': 'alerta', 'titulo': 'Endividamento Excessivo',
                'descricao': f"O endividamento total representa {metricas['endividamento_anual']:.1f} vezes o rendimento anual.",
                'acao': 'Plano de Reducao', 'impacto': 'Focar em amortizar creditos com taxas mais altas'
            })
        cartoes = [c for c in creditos if 'cartao' in c['produto'].lower()]
        if len(cartoes) > 2:
            recomendacoes.append({
                'tipo': 'info', 'titulo': 'Multiplos Cartoes de Credito',
                'descricao': f"Possui {len(cartoes)} cartoes de credito.",
                'acao': 'Cancelar Cartoes', 'impacto': 'Melhorar capacidade de endividamento'
            })
        if metricas['score'] >= 80 and metricas['taxa_esforco'] < 20:
            recomendacoes.append({
                'tipo': 'sucesso', 'titulo': 'Perfil Financeiro Saudavel',
                'descricao': "Excelente gestao financeira! Considera antecipar capital em creditos com taxas mais altas.",
                'acao': 'Amortizar Creditos', 'impacto': 'Poupanca de juros a longo prazo'
            })
        fiadores = [c for c in creditos if c.get('fiadores')]
        if fiadores:
            recomendacoes.append({
                'tipo': 'info', 'titulo': 'Responsabilidades como Fiador/Avalista',
                'descricao': f"E fiador/avalista em {len(fiadores)} credito(s).",
                'acao': 'Monitorizar', 'impacto': 'Verificar regularidade dos creditos garantidos'
            })
        return recomendacoes

    def criar_graficos(self, creditos, metricas):
        graficos = {}
        if not creditos:
            return graficos

        df = pd.DataFrame(creditos)

        # 1. Divida por Entidade
        df_entidades = df.groupby('entidade')['montante_divida'].sum().reset_index()
        df_entidades = df_entidades.sort_values('montante_divida', ascending=True)
        fig1 = px.bar(df_entidades, x='montante_divida', y='entidade', orientation='h',
                     title='Divida Total por Entidade',
                     labels={'montante_divida': 'Montante em Divida (EUR)', 'entidade': 'Entidade'},
                     color='montante_divida', color_continuous_scale='Reds')
        fig1.update_layout(height=400)
        graficos['divida_entidade'] = json.dumps(fig1, cls=PlotlyJSONEncoder)

        # 2. Pizza por Produto
        df_produtos = df.groupby('produto')['montante_divida'].sum().reset_index()
        fig2 = px.pie(df_produtos, values='montante_divida', names='produto',
                     title='Distribuicao da Divida por Tipo de Produto', hole=0.4,
                     color_discrete_sequence=px.colors.sequential.RdBu)
        fig2.update_layout(height=400)
        graficos['divida_produto'] = json.dumps(fig2, cls=PlotlyJSONEncoder)

        # 3. Gauge Taxa de Esforco
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=metricas['taxa_esforco'],
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Taxa de Esforco (%)", 'font': {'size': 24}},
            delta={'reference': 30, 'increasing': {'color': "#dc3545"}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1},
                'bar': {'color': metricas['cor_classificacao']},
                'steps': [
                    {'range': [0, 30], 'color': '#d4edda'},
                    {'range': [30, 40], 'color': '#fff3cd'},
                    {'range': [40, 60], 'color': '#f8d7da'},
                    {'range': [60, 100], 'color': '#721c24'}
                ],
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': 40}
            }
        ))
        fig3.update_layout(height=350)
        graficos['gauge_esforco'] = json.dumps(fig3, cls=PlotlyJSONEncoder)

        # 4. Prestacoes Mensais
        df_ativos = df[df['situacao'] != 'Liquidado'].copy()
        if not df_ativos.empty:
            fig4 = px.bar(df_ativos, x='entidade', y='prestacao_mensal', color='situacao',
                         title='Prestacoes Mensais por Entidade',
                         labels={'prestacao_mensal': 'Prestacao (EUR)', 'entidade': 'Entidade'},
                         color_discrete_map={'Regular': '#28a745', 'Incumprimento': '#dc3545', 'Litigio Judicial': '#fd7e14'})
            fig4.update_layout(height=400, xaxis_tickangle=-45)
            graficos['prestacoes'] = json.dumps(fig4, cls=PlotlyJSONEncoder)

        return graficos


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    file = request.files['file']
    rendimento = request.form.get('rendimento', 2000)
    try:
        rendimento = float(rendimento)
    except:
        rendimento = 2000
    if file.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    if file and allowed_file(file.filename):
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        try:
            analyzer = CRCAnalyzer()
            dados = analyzer.extrair_dados_pdf(filepath)
            if not dados['creditos']:
                dados['creditos'] = gerar_dados_demo()
                dados['demo_mode'] = True
            else:
                dados['demo_mode'] = False
            metricas = analyzer.calcular_metricas(dados['creditos'], rendimento)
            recomendacoes = analyzer.gerar_recomendacoes(dados['creditos'], metricas)
            graficos = analyzer.criar_graficos(dados['creditos'], metricas)
            for c in dados['creditos']:
                for key, val in c.items():
                    if isinstance(val, float):
                        c[key] = round(val, 2)
            response = {
                'success': True, 'titular': dados['titular'],
                'data_consulta': dados['data_consulta'],
                'demo_mode': dados.get('demo_mode', False),
                'creditos': dados['creditos'], 'metricas': metricas,
                'recomendacoes': recomendacoes, 'graficos': graficos,
                'resumo': {
                    'total_creditos': len(dados['creditos']),
                    'total_divida': sum(c['montante_divida'] for c in dados['creditos']),
                    'total_prestacoes': sum(c['prestacao_mensal'] for c in dados['creditos'] if c['situacao'] != 'Liquidado'),
                    'n_incumprimentos': len([c for c in dados['creditos'] if c['situacao'] == 'Incumprimento'])
                }
            }
            os.remove(filepath)
            return jsonify(response)
        except Exception as e:
            import traceback
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Erro ao processar PDF: {str(e)}', 'trace': traceback.format_exc()}), 500
    return jsonify({'error': 'Formato de arquivo invalido. Use PDF.'}), 400


def gerar_dados_demo():
    return [
        {'entidade': 'Banco Santander Totta', 'produto': 'Credito Habitacao', 'tipo_negociacao': 'HAB-2020-001',
         'data_inicio': '15/03/2020', 'data_fim': '15/03/2050', 'montante_inicial': 150000.0,
         'montante_divida': 135420.50, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 580.25, 'taxa_juro': 1.25, 'prazo_total': 360, 'prazo_restante': 324,
         'situacao': 'Regular', 'garantias': ['Hipoteca'], 'fiadores': []},
        {'entidade': 'Caixa Geral de Depositos', 'produto': 'Credito Automovel', 'tipo_negociacao': 'AUT-2022-045',
         'data_inicio': '10/06/2022', 'data_fim': '10/06/2027', 'montante_inicial': 25000.0,
         'montante_divida': 18500.00, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 420.00, 'taxa_juro': 5.99, 'prazo_total': 60, 'prazo_restante': 42,
         'situacao': 'Regular', 'garantias': ['Penhor do veiculo'], 'fiadores': []},
        {'entidade': 'Millennium BCP', 'produto': 'Cartao de Credito', 'tipo_negociacao': 'CC-2021-123',
         'data_inicio': '01/01/2021', 'data_fim': '', 'montante_inicial': 5000.0,
         'montante_divida': 3200.00, 'montante_vencido': 450.00, 'montante_abatido': 0.0,
         'prestacao_mensal': 150.00, 'taxa_juro': 18.99, 'prazo_total': 0, 'prazo_restante': 0,
         'situacao': 'Incumprimento', 'garantias': [], 'fiadores': []},
        {'entidade': 'Novo Banco', 'produto': 'Credito Pessoal', 'tipo_negociacao': 'CP-2023-089',
         'data_inicio': '20/09/2023', 'data_fim': '20/09/2028', 'montante_inicial': 15000.0,
         'montante_divida': 12800.00, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 285.50, 'taxa_juro': 8.50, 'prazo_total': 60, 'prazo_restante': 48,
         'situacao': 'Regular', 'garantias': [], 'fiadores': ['Maria Silva']},
        {'entidade': 'Banco Santander Totta', 'produto': 'Cartao de Credito', 'tipo_negociacao': 'CC-2019-567',
         'data_inicio': '05/12/2019', 'data_fim': '', 'montante_inicial': 3000.0,
         'montante_divida': 0.0, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 0.0, 'taxa_juro': 19.50, 'prazo_total': 0, 'prazo_restante': 0,
         'situacao': 'Liquidado', 'garantias': [], 'fiadores': []}
    ]


os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
