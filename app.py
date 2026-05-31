
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
        """Extrai dados do PDF do CRC do Banco de Portugal"""
        dados_extraidos = {
            'titular': '',
            'data_consulta': '',
            'creditos': [],
            'resumo': {}
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Extrair titular da primeira página
                primeira_pagina = pdf.pages[0]
                texto_primeira = primeira_pagina.extract_text() or ""
                dados_extraidos['titular'] = self._extrair_titular(texto_primeira)
                dados_extraidos['data_consulta'] = self._extrair_data_consulta(texto_primeira)

                # Extrair créditos de cada página
                for i, page in enumerate(pdf.pages):
                    texto = page.extract_text() or ""

                    # Verificar se é página de crédito detalhado (não resumo)
                    if 'Informação comunicada pela instituição' in texto or                        'Informação comunicada pela instituição' in texto:
                        credito = self._extrair_credito_pagina(texto)
                        if credito and credito['entidade']:
                            dados_extraidos['creditos'].append(credito)

                # Se não encontrou créditos, tentar método alternativo
                if not dados_extraidos['creditos']:
                    for i, page in enumerate(pdf.pages):
                        texto = page.extract_text() or ""
                        credito = self._extrair_credito_texto_livre(texto)
                        if credito and credito['entidade']:
                            dados_extraidos['creditos'].append(credito)

        except Exception as e:
            print(f"Erro na extração: {e}")

        return dados_extraidos

    def _extrair_titular(self, texto):
        """Extrai nome do titular do texto"""
        # Formato: "Nome:CATIA CAROLINA BRANCO BARBOSA"
        match = re.search(r'Nome[:\s]+([A-Z][A-Z\s]+[A-Z])', texto)
        if match:
            return match.group(1).strip()
        # Fallback
        match = re.search(r'Nome[:\s]+([\w\s]+)', texto)
        if match:
            return match.group(1).strip()
        return "Titular não identificado"

    def _extrair_data_consulta(self, texto):
        """Extrai data da consulta"""
        # Formato: "Data de Emissão:08-03-2020 13:11:44"
        match = re.search(r'Data de Emiss[ãa]o[:\s]+(\d{2}-\d{2}-\d{4})', texto)
        if match:
            data = match.group(1)
            return data.replace('-', '/')
        # Outros formatos
        match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
        if match:
            return match.group(1)
        return datetime.now().strftime("%d/%m/%Y")

    def _extrair_credito_pagina(self, texto):
        """Extrai um crédito de uma página do CRC"""
        credito = {
            'entidade': '', 'produto': '', 'tipo_negociacao': '',
            'data_inicio': '', 'data_fim': '', 'montante_inicial': 0.0,
            'montante_divida': 0.0, 'montante_vencido': 0.0,
            'montante_abatido': 0.0, 'prestacao_mensal': 0.0,
            'taxa_juro': 0.0, 'prazo_total': 0, 'prazo_restante': 0,
            'situacao': 'Regular', 'garantias': [], 'fiadores': []
        }

        # Entidade - formato: "Informação comunicada pela instituição:BANCO BNP PARIBAS PERSONAL FINANCE,SA (0848)"
        match = re.search(r'Informa[cç][ãa]o comunicada pela institui[cç][ãa]o[:\s]+(.+?)(?:\s*\(|
)', texto)
        if match:
            credito['entidade'] = match.group(1).strip()

        # Produto financeiro
        match = re.search(r'Produto financeiro[:\s]+(.+?)(?:
|Tipo de neg)', texto)
        if match:
            credito['produto'] = match.group(1).strip()

        # Tipo de negociação
        match = re.search(r'Tipo de negocia[cç][ãa]o[:\s]+(.+?)(?:
|Início)', texto)
        if match:
            credito['tipo_negociacao'] = match.group(1).strip()

        # Data de início
        match = re.search(r'Início[:\s]+(\d{4}-\d{2}-\d{2})', texto)
        if match:
            data = match.group(1)
            credito['data_inicio'] = f"{data[8:10]}/{data[5:7]}/{data[0:4]}"

        # Data de fim
        match = re.search(r'Fim[:\s]+(\d{4}-\d{2}-\d{2})', texto)
        if match:
            data = match.group(1)
            credito['data_fim'] = f"{data[8:10]}/{data[5:7]}/{data[0:4]}"

        # Total em dívida
        match = re.search(r'Total em d[íi]vida[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            credito['montante_divida'] = self._parse_montante(match.group(1))

        # Em incumprimento
        match = re.search(r'em incumprimento[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            val = self._parse_montante(match.group(1))
            if val > 0:
                credito['situacao'] = 'Incumprimento'

        # Vencido
        match = re.search(r'Vencido[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            credito['montante_vencido'] = self._parse_montante(match.group(1))

        # Abatido ao ativo
        match = re.search(r'Abatido ao ativo[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            credito['montante_abatido'] = self._parse_montante(match.group(1))

        # Prestação
        match = re.search(r'Presta[cç][ãa]o[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            credito['prestacao_mensal'] = self._parse_montante(match.group(1))

        # Montante potencial (responsabilidade potencial)
        match = re.search(r'Potencial[:\s]+([\d\.,]+)\s*€', texto)
        if match:
            credito['montante_inicial'] = self._parse_montante(match.group(1))

        # Período de free-float (para cartões)
        if 'free-float' in texto.lower():
            if 'com período de free-float' in texto.lower():
                credito['produto'] = 'Cartão de crédito - com período de free-float'
            elif 'sem período de free-float' in texto.lower():
                credito['produto'] = 'Cartão de crédito - sem período de free-float'

        # Em litígio judicial
        if 'Em litígio judicial' in texto or 'Em litígio judicial' in texto:
            credito['situacao'] = 'Litígio Judicial'

        return credito

    def _extrair_credito_texto_livre(self, texto):
        """Método alternativo de extração"""
        credito = {
            'entidade': '', 'produto': '', 'tipo_negociacao': '',
            'data_inicio': '', 'data_fim': '', 'montante_inicial': 0.0,
            'montante_divida': 0.0, 'montante_vencido': 0.0,
            'montante_abatido': 0.0, 'prestacao_mensal': 0.0,
            'taxa_juro': 0.0, 'prazo_total': 0, 'prazo_restante': 0,
            'situacao': 'Regular', 'garantias': [], 'fiadores': []
        }

        # Procurar por padrões no texto
        linhas = texto.split('\n')

        for i, linha in enumerate(linhas):
            # Entidade
            if 'BANCO' in linha.upper() and 'instituição' in linha.lower():
                match = re.search(r'BANCO\s+[^
]+', linha)
                if match:
                    credito['entidade'] = match.group(0).strip()

            # Produto
            if 'Produto financeiro' in linha:
                match = re.search(r'Produto financeiro[:\s]+(.+)', linha)
                if match:
                    credito['produto'] = match.group(1).strip()

            # Valores monetários
            valores = re.findall(r'([\d\.,]+)\s*€', linha)
            if valores:
                # Atribuir valores baseado no contexto
                if 'dívida' in linha.lower():
                    credito['montante_divida'] = self._parse_montante(valores[0])
                elif 'prestação' in linha.lower():
                    credito['prestacao_mensal'] = self._parse_montante(valores[0])
                elif 'vencido' in linha.lower():
                    credito['montante_vencido'] = self._parse_montante(valores[0])

        return credito

    def _parse_montante(self, valor_str):
        """Converte string de montante para float"""
        if not valor_str:
            return 0.0
        limpo = re.sub(r'[^\d,\.]', '', str(valor_str))
        limpo = limpo.replace('.', '').replace(',', '.')
        try:
            return float(limpo) if limpo else 0.0
        except:
            return 0.0

    def calcular_metricas(self, creditos, rendimento_mensal=2000):
        """Calcula métricas financeiras"""
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
            classificacao, cor = 'Atenção', '#ffc107'
        elif score >= 20:
            classificacao, cor = 'Risco', '#fd7e14'
        else:
            classificacao, cor = 'Crítico', '#dc3545'

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
        """Gera recomendações personalizadas"""
        recomendacoes = []
        if metricas['taxa_esforco'] > 40:
            recomendacoes.append({
                'tipo': 'urgente', 'titulo': 'Taxa de Esforço Crítica',
                'descricao': f"A taxa de esforço está em {metricas['taxa_esforco']}%, muito acima do limite recomendado de 30-35%.",
                'acao': 'Consolidar Créditos', 'impacto': 'Reduzir prestações mensais em 20-40%'
            })
        elif metricas['taxa_esforco'] > 30:
            recomendacoes.append({
                'tipo': 'alerta', 'titulo': 'Taxa de Esforço Elevada',
                'descricao': f"Taxa de esforço de {metricas['taxa_esforco']}% está acima do recomendado.",
                'acao': 'Renegociar Prazos', 'impacto': 'Reduzir prestações em 10-20%'
            })
        if metricas['n_incumprimentos'] > 0:
            recomendacoes.append({
                'tipo': 'urgente', 'titulo': f"{metricas['n_incumprimentos']} Crédito(s) em Incumprimento",
                'descricao': f"Existem {metricas['n_incumprimentos']} créditos em incumprimento com {metricas['total_vencido']:,.2f}€ vencidos.",
                'acao': 'Regularizar Dívidas', 'impacto': 'Evitar registo negativo no Banco de Portugal'
            })
        if metricas['endividamento_anual'] > 3:
            recomendacoes.append({
                'tipo': 'alerta', 'titulo': 'Endividamento Excessivo',
                'descricao': f"O endividamento total representa {metricas['endividamento_anual']:.1f} vezes o rendimento anual.",
                'acao': 'Plano de Redução', 'impacto': 'Focar em amortizar créditos com taxas mais altas'
            })
        cartoes = [c for c in creditos if 'cartão' in c['produto'].lower()]
        if len(cartoes) > 2:
            recomendacoes.append({
                'tipo': 'info', 'titulo': 'Múltiplos Cartões de Crédito',
                'descricao': f"Possui {len(cartoes)} cartões de crédito.",
                'acao': 'Cancelar Cartões', 'impacto': 'Melhorar capacidade de endividamento'
            })
        if metricas['score'] >= 80 and metricas['taxa_esforco'] < 20:
            recomendacoes.append({
                'tipo': 'sucesso', 'titulo': 'Perfil Financeiro Saudável',
                'descricao': "Excelente gestão financeira! Considera antecipar capital em créditos com taxas mais altas.",
                'acao': 'Amortizar Créditos', 'impacto': 'Poupança de juros a longo prazo'
            })
        fiadores = [c for c in creditos if c.get('fiadores')]
        if fiadores:
            recomendacoes.append({
                'tipo': 'info', 'titulo': 'Responsabilidades como Fiador/Avalista',
                'descricao': f"É fiador/avalista em {len(fiadores)} crédito(s).",
                'acao': 'Monitorizar', 'impacto': 'Verificar regularidade dos créditos garantidos'
            })
        return recomendacoes

    def criar_graficos(self, creditos, metricas):
        """Cria gráficos interativos com Plotly"""
        graficos = {}
        if not creditos:
            return graficos

        df = pd.DataFrame(creditos)

        # 1. Dívida por Entidade
        df_entidades = df.groupby('entidade')['montante_divida'].sum().reset_index()
        df_entidades = df_entidades.sort_values('montante_divida', ascending=True)
        fig1 = px.bar(df_entidades, x='montante_divida', y='entidade', orientation='h',
                     title='Dívida Total por Entidade',
                     labels={'montante_divida': 'Montante em Dívida (€)', 'entidade': 'Entidade'},
                     color='montante_divida', color_continuous_scale='Reds')
        fig1.update_layout(height=400)
        graficos['divida_entidade'] = json.dumps(fig1, cls=PlotlyJSONEncoder)

        # 2. Pizza por Produto
        df_produtos = df.groupby('produto')['montante_divida'].sum().reset_index()
        fig2 = px.pie(df_produtos, values='montante_divida', names='produto',
                     title='Distribuição da Dívida por Tipo de Produto', hole=0.4,
                     color_discrete_sequence=px.colors.sequential.RdBu)
        fig2.update_layout(height=400)
        graficos['divida_produto'] = json.dumps(fig2, cls=PlotlyJSONEncoder)

        # 3. Gauge Taxa de Esforço
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=metricas['taxa_esforco'],
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Taxa de Esforço (%)", 'font': {'size': 24}},
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

        # 4. Prestações Mensais
        df_ativos = df[df['situacao'] != 'Liquidado'].copy()
        if not df_ativos.empty:
            fig4 = px.bar(df_ativos, x='entidade', y='prestacao_mensal', color='situacao',
                         title='Prestações Mensais por Entidade',
                         labels={'prestacao_mensal': 'Prestação (€)', 'entidade': 'Entidade'},
                         color_discrete_map={'Regular': '#28a745', 'Incumprimento': '#dc3545', 'Litígio Judicial': '#fd7e14'})
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
    return jsonify({'error': 'Formato de arquivo inválido. Use PDF.'}), 400


def gerar_dados_demo():
    return [
        {'entidade': 'Banco Santander Totta', 'produto': 'Crédito Habitação', 'tipo_negociacao': 'HAB-2020-001',
         'data_inicio': '15/03/2020', 'data_fim': '15/03/2050', 'montante_inicial': 150000.0,
         'montante_divida': 135420.50, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 580.25, 'taxa_juro': 1.25, 'prazo_total': 360, 'prazo_restante': 324,
         'situacao': 'Regular', 'garantias': ['Hipoteca'], 'fiadores': []},
        {'entidade': 'Caixa Geral de Depósitos', 'produto': 'Crédito Automóvel', 'tipo_negociacao': 'AUT-2022-045',
         'data_inicio': '10/06/2022', 'data_fim': '10/06/2027', 'montante_inicial': 25000.0,
         'montante_divida': 18500.00, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 420.00, 'taxa_juro': 5.99, 'prazo_total': 60, 'prazo_restante': 42,
         'situacao': 'Regular', 'garantias': ['Penhor do veículo'], 'fiadores': []},
        {'entidade': 'Millennium BCP', 'produto': 'Cartão de Crédito', 'tipo_negociacao': 'CC-2021-123',
         'data_inicio': '01/01/2021', 'data_fim': '', 'montante_inicial': 5000.0,
         'montante_divida': 3200.00, 'montante_vencido': 450.00, 'montante_abatido': 0.0,
         'prestacao_mensal': 150.00, 'taxa_juro': 18.99, 'prazo_total': 0, 'prazo_restante': 0,
         'situacao': 'Incumprimento', 'garantias': [], 'fiadores': []},
        {'entidade': 'Novo Banco', 'produto': 'Crédito Pessoal', 'tipo_negociacao': 'CP-2023-089',
         'data_inicio': '20/09/2023', 'data_fim': '20/09/2028', 'montante_inicial': 15000.0,
         'montante_divida': 12800.00, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 285.50, 'taxa_juro': 8.50, 'prazo_total': 60, 'prazo_restante': 48,
         'situacao': 'Regular', 'garantias': [], 'fiadores': ['Maria Silva']},
        {'entidade': 'Banco Santander Totta', 'produto': 'Cartão de Crédito', 'tipo_negociacao': 'CC-2019-567',
         'data_inicio': '05/12/2019', 'data_fim': '', 'montante_inicial': 3000.0,
         'montante_divida': 0.0, 'montante_vencido': 0.0, 'montante_abatido': 0.0,
         'prestacao_mensal': 0.0, 'taxa_juro': 19.50, 'prazo_total': 0, 'prazo_restante': 0,
         'situacao': 'Liquidado', 'garantias': [], 'fiadores': []}
    ]


# Criar pasta uploads na inicialização
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
