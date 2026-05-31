
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import os
import re
import json
from datetime import datetime
import pandas as pd
import pdfplumber
import io
import base64
import plotly.express as px
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
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
        """Extrai dados do PDF do CRC usando pdfplumber"""
        dados_extraidos = {
            'titular': '',
            'data_consulta': '',
            'creditos': [],
            'resumo': {}
        }

        try:
            with pdfplumber.open(pdf_path) as pdf:
                texto_completo = ""
                for page in pdf.pages:
                    texto = page.extract_text()
                    if texto:
                        texto_completo += texto + "\n"

                # Extrair informações do titular
                dados_extraidos['titular'] = self._extrair_titular(texto_completo)
                dados_extraidos['data_consulta'] = self._extrair_data_consulta(texto_completo)

                # Extrair tabelas de créditos
                tabelas = self._extrair_tabelas_pdfplumber(pdf)

                if tabelas and len(tabelas) > 0:
                    dados_extraidos['creditos'] = self._parse_tabelas_creditos(tabelas)
                else:
                    # Tentar extrair do texto como fallback
                    dados_extraidos['creditos'] = self._extrair_creditos_texto(texto_completo)

        except Exception as e:
            print(f"Erro na extração: {e}")

        return dados_extraidos

    def _extrair_titular(self, texto):
        """Extrai nome do titular do texto"""
        padroes = [
            r'(?:Titular|Nome|Cliente):?\s*([A-Z][a-zA-Z\s]+)(?=\n|Data|NIF)',
            r'([A-Z][A-Z\s]+[A-Z])\s*(?:Data de Nascimento|NIF)',
        ]
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "Titular não identificado"

    def _extrair_data_consulta(self, texto):
        """Extrai data da consulta"""
        padroes = [
            r'Data(?:\s*da)?\s*Consulta:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(?:Consulta|Emissão)\s*em:?\s*(\d{2}[/-]\d{2}[/-]\d{4})',
            r'(\d{2}/\d{2}/\d{4})\s*(?:Mapa|CRC)',
        ]
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                return match.group(1)
        return datetime.now().strftime("%d/%m/%Y")

    def _extrair_tabelas_pdfplumber(self, pdf):
        """Extrai tabelas do PDF usando pdfplumber"""
        todas_tabelas = []
        for page in pdf.pages:
            tabelas = page.extract_tables()
            for tabela in tabelas:
                if tabela and len(tabela) > 1:
                    todas_tabelas.append(tabela)
        return todas_tabelas

    def _parse_tabelas_creditos(self, tabelas):
        """Parse das tabelas extraídas para formato estruturado"""
        creditos = []

        for tabela in tabelas:
            if not tabela or len(tabela) < 2:
                continue

            # Identificar cabeçalho
            header = tabela[0]
            header_lower = [str(h).lower() if h else '' for h in header]

            # Verificar se é tabela de créditos
            if any(keyword in ' '.join(header_lower) for keyword in 
                   ['entidade', 'produto', 'montante', 'dívida', 'prestação', 'situação']):

                for row in tabela[1:]:
                    if len(row) < 3:
                        continue

                    credito = self._parse_linha_credito(row, header)
                    if credito:
                        creditos.append(credito)

        return creditos

    def _parse_linha_credito(self, row, header):
        """Parse de uma linha de crédito"""
        credito = {
            'entidade': '',
            'produto': '',
            'tipo_negociacao': '',
            'data_inicio': '',
            'data_fim': '',
            'montante_inicial': 0.0,
            'montante_divida': 0.0,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 0.0,
            'taxa_juro': 0.0,
            'prazo_total': 0,
            'prazo_restante': 0,
            'situacao': 'Regular',
            'garantias': [],
            'fiadores': []
        }

        # Mapear colunas com base no cabeçalho
        for i, (col_name, value) in enumerate(zip(header, row)):
            if not col_name or not value:
                continue

            col_lower = str(col_name).lower().strip()
            val_str = str(value).strip()

            if any(k in col_lower for k in ['entidade', 'instituição', 'credor']):
                credito['entidade'] = val_str
            elif any(k in col_lower for k in ['produto', 'tipo', 'modalidade']):
                credito['produto'] = val_str
            elif any(k in col_lower for k in ['negociação', 'contrato', 'nº']):
                credito['tipo_negociacao'] = val_str
            elif any(k in col_lower for k in ['início', 'contratação', 'data início']):
                credito['data_inicio'] = val_str
            elif any(k in col_lower for k in ['fim', 'vencimento', 'data fim']):
                credito['data_fim'] = val_str
            elif any(k in col_lower for k in ['inicial', 'capital', 'montante inicial']):
                credito['montante_inicial'] = self._parse_montante(val_str)
            elif any(k in col_lower for k in ['dívida', 'saldo', 'montante em dívida', 'responsabilidade efetiva']):
                credito['montante_divida'] = self._parse_montante(val_str)
            elif any(k in col_lower for k in ['vencido', 'em incumprimento', 'vencimentos']):
                credito['montante_vencido'] = self._parse_montante(val_str)
            elif any(k in col_lower for k in ['abatido', 'perdido', 'abatido ao ativo']):
                credito['montante_abatido'] = self._parse_montante(val_str)
            elif any(k in col_lower for k in ['prestação', 'mensalidade', 'pagamento']):
                credito['prestacao_mensal'] = self._parse_montante(val_str)
            elif any(k in col_lower for k in ['taxa', 'juro', 'euribor', 'spread']):
                credito['taxa_juro'] = self._parse_taxa(val_str)
            elif any(k in col_lower for k in ['prazo', 'duração', 'tempo']):
                prazo = self._parse_prazo(val_str)
                if prazo:
                    credito['prazo_total'] = prazo
            elif any(k in col_lower for k in ['situação', 'estado', 'regularidade']):
                credito['situacao'] = self._parse_situacao(val_str)
            elif any(k in col_lower for k in ['garantia', 'código garantia']):
                credito['garantias'] = self._parse_garantias(val_str)
            elif any(k in col_lower for k in ['fiador', 'avalista', 'garante']):
                credito['fiadores'] = self._parse_fiadores(val_str)

        # Só retorna se tiver entidade e produto identificados
        if credito['entidade'] and credito['produto']:
            return credito
        return None

    def _parse_montante(self, valor_str):
        """Converte string de montante para float"""
        if not valor_str:
            return 0.0
        # Remover símbolos e converter
        limpo = re.sub(r'[^\d,\.]', '', str(valor_str))
        # Tratar formato português (1.234,56)
        limpo = limpo.replace('.', '').replace(',', '.')
        try:
            return float(limpo) if limpo else 0.0
        except:
            return 0.0

    def _parse_taxa(self, taxa_str):
        """Extrai taxa de juro da string"""
        if not taxa_str:
            return 0.0
        match = re.search(r'(\d+[.,]?\d*)\s*%', str(taxa_str))
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except:
                return 0.0
        return 0.0

    def _parse_prazo(self, prazo_str):
        """Extrai prazo em meses"""
        if not prazo_str:
            return 0
        match = re.search(r'(\d+)', str(prazo_str))
        if match:
            return int(match.group(1))
        return 0

    def _parse_situacao(self, sit_str):
        """Normaliza situação do crédito"""
        sit_lower = str(sit_str).lower()
        if any(k in sit_lower for k in ['incumprimento', 'vencido', 'irregular', 'atraso', 'default']):
            return 'Incumprimento'
        elif any(k in sit_lower for k in ['regular', 'normal', 'em dia']):
            return 'Regular'
        elif any(k in sit_lower for k in ['liquidado', 'pago', 'encerrado']):
            return 'Liquidado'
        return 'Regular'

    def _parse_garantias(self, gar_str):
        """Parse das garantias"""
        if not gar_str:
            return []
        return [g.strip() for g in str(gar_str).split(',') if g.strip()]

    def _parse_fiadores(self, fia_str):
        """Parse dos fiadores"""
        if not fia_str:
            return []
        return [f.strip() for f in str(fia_str).split(',') if f.strip()]

    def _extrair_creditos_texto(self, texto):
        """Extrai créditos do texto como fallback"""
        creditos = []
        # Padrões para encontrar blocos de crédito no texto
        linhas = texto.split('\n')

        for i, linha in enumerate(linhas):
            # Procurar por linhas que parecem ter dados de crédito
            if any(entidade in linha for entidade in ['Banco', 'Caixa', 'Millennium', 'Novo Banco', 'Santander', 'CGD', 'BCP']):
                # Tentar extrair dados da linha atual e próximas
                credito = self._parse_bloco_credito(linhas, i)
                if credito:
                    creditos.append(credito)

        return creditos

    def _parse_bloco_credito(self, linhas, idx):
        """Parse de um bloco de crédito do texto"""
        credito = {
            'entidade': '',
            'produto': '',
            'tipo_negociacao': '',
            'data_inicio': '',
            'data_fim': '',
            'montante_inicial': 0.0,
            'montante_divida': 0.0,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 0.0,
            'taxa_juro': 0.0,
            'prazo_total': 0,
            'prazo_restante': 0,
            'situacao': 'Regular',
            'garantias': [],
            'fiadores': []
        }

        # Extrair entidade da linha atual
        linha = linhas[idx]
        credito['entidade'] = linha.strip()[:50]

        # Procurar produto nas próximas linhas
        for j in range(idx+1, min(idx+5, len(linhas))):
            linha_j = linhas[j]
            if any(prod in linha_j.lower() for prod in ['habitação', 'automóvel', 'crédito pessoal', 'cartão']):
                credito['produto'] = linha_j.strip()[:50]
                break

        # Procurar valores monetários
        valores = re.findall(r'(\d[\d\s.,]+)\s*[€]?', ' '.join(linhas[idx:idx+10]))
        if len(valores) >= 2:
            credito['montante_divida'] = self._parse_montante(valores[0])
            credito['prestacao_mensal'] = self._parse_montante(valores[-1])

        if credito['entidade'] and credito['produto']:
            return credito
        return None

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

        # Taxa de esforço
        taxa_esforco = (total_prestacoes / rendimento_mensal * 100) if rendimento_mensal > 0 else 0

        # Endividamento anual
        endividamento_anual = total_divida / (rendimento_mensal * 12) if rendimento_mensal > 0 else 0

        # Rácio de incumprimento
        risco_incumprimento = (total_vencido / total_divida * 100) if total_divida > 0 else 0

        # Score de saúde financeira (0-100)
        score = 100
        score -= min(taxa_esforco * 1.5, 40)  # Penalizar taxa de esforço
        score -= min(endividamento_anual * 10, 25)  # Penalizar endividamento
        score -= min(n_incumprimentos * 15, 30)  # Penalizar incumprimentos
        score -= min(risco_incumprimento * 2, 20)  # Penalizar valor vencido
        score = max(0, min(100, score))

        # Classificação
        if score >= 80:
            classificacao = 'Excelente'
            cor = '#28a745'
        elif score >= 60:
            classificacao = 'Bom'
            cor = '#6c757d'
        elif score >= 40:
            classificacao = 'Atenção'
            cor = '#ffc107'
        elif score >= 20:
            classificacao = 'Risco'
            cor = '#fd7e14'
        else:
            classificacao = 'Crítico'
            cor = '#dc3545'

        return {
            'total_divida': total_divida,
            'total_vencido': total_vencido,
            'total_abatido': total_abatido,
            'total_prestacoes': total_prestacoes,
            'n_creditos_ativos': n_creditos,
            'n_incumprimentos': n_incumprimentos,
            'taxa_esforco': round(taxa_esforco, 2),
            'endividamento_anual': round(endividamento_anual, 2),
            'risco_incumprimento': round(risco_incumprimento, 2),
            'score': round(score, 1),
            'classificacao': classificacao,
            'cor_classificacao': cor,
            'rendimento_mensal': rendimento_mensal
        }

    def gerar_recomendacoes(self, creditos, metricas):
        """Gera recomendações personalizadas"""
        recomendacoes = []

        # Recomendações baseadas na taxa de esforço
        if metricas['taxa_esforco'] > 40:
            recomendacoes.append({
                'tipo': 'urgente',
                'titulo': 'Taxa de Esforço Crítica',
                'descricao': f"A taxa de esforço está em {metricas['taxa_esforco']}%, muito acima do limite recomendado de 30-35%. Considere urgentemente renegociar prazos ou consolidar créditos.",
                'acao': 'Consolidar Créditos',
                'impacto': 'Reduzir prestações mensais em 20-40%'
            })
        elif metricas['taxa_esforco'] > 30:
            recomendacoes.append({
                'tipo': 'alerta',
                'titulo': 'Taxa de Esforço Elevada',
                'descricao': f"Taxa de esforço de {metricas['taxa_esforco']}% está acima do recomendado. Avalie a possibilidade de renegociação.",
                'acao': 'Renegociar Prazos',
                'impacto': 'Reduzir prestações em 10-20%'
            })

        # Recomendações sobre incumprimentos
        if metricas['n_incumprimentos'] > 0:
            recomendacoes.append({
                'tipo': 'urgente',
                'titulo': f"{metricas['n_incumprimentos']} Crédito(s) em Incumprimento",
                'descricao': f"Existem {metricas['n_incumprimentos']} créditos em situação de incumprimento com {metricas['total_vencido']:,.2f}€ vencidos. Contacte as entidades para regularização imediata.",
                'acao': 'Regularizar Dívidas',
                'impacto': 'Evitar registo negativo no Banco de Portugal'
            })

        # Recomendações sobre endividamento
        if metricas['endividamento_anual'] > 3:
            recomendacoes.append({
                'tipo': 'alerta',
                'titulo': 'Endividamento Excessivo',
                'descricao': f"O endividamento total representa {metricas['endividamento_anual']:.1f} vezes o rendimento anual. O ideal é manter abaixo de 3x.",
                'acao': 'Plano de Redução',
                'impacto': 'Focar em amortizar créditos com taxas mais altas'
            })

        # Recomendações por tipo de crédito
        cartoes = [c for c in creditos if 'cartão' in c['produto'].lower()]
        if len(cartoes) > 2:
            recomendacoes.append({
                'tipo': 'info',
                'titulo': 'Múltiplos Cartões de Crédito',
                'descricao': f"Possui {len(cartoes)} cartões de crédito. Mesmo sem utilização, estas responsabilidades potenciais podem dificultar novos créditos.",
                'acao': 'Cancelar Cartões',
                'impacto': 'Melhorar capacidade de endividamento para habitação'
            })

        # Recomendações para perfis saudáveis
        if metricas['score'] >= 80 and metricas['taxa_esforco'] < 20:
            recomendacoes.append({
                'tipo': 'sucesso',
                'titulo': 'Perfil Financeiro Saudável',
                'descricao': "Excelente gestão financeira! Considera antecipar capital em créditos com taxas mais altas para poupar juros.",
                'acao': 'Amortizar Créditos',
                'impacto': 'Poupança de juros a longo prazo'
            })

        # Recomendação sobre fiadores
        fiadores = [c for c in creditos if c.get('fiadores')]
        if fiadores:
            recomendacoes.append({
                'tipo': 'info',
                'titulo': 'Responsabilidades como Fiador/Avalista',
                'descricao': f"É fiador/avalista em {len(fiadores)} crédito(s). Estas responsabilidades potenciais contam para a sua capacidade de endividamento.",
                'acao': 'Monitorizar',
                'impacto': 'Verificar regularidade dos créditos garantidos'
            })

        return recomendacoes

    def criar_graficos(self, creditos, metricas):
        """Cria gráficos interativos com Plotly"""
        graficos = {}

        if not creditos:
            return graficos

        df = pd.DataFrame(creditos)

        # 1. Gráfico de barras - Dívida por Entidade
        df_entidades = df.groupby('entidade')['montante_divida'].sum().reset_index()
        df_entidades = df_entidades.sort_values('montante_divida', ascending=True)

        fig1 = px.bar(df_entidades, 
                     x='montante_divida', 
                     y='entidade',
                     orientation='h',
                     title='Dívida Total por Entidade',
                     labels={'montante_divida': 'Montante em Dívida (€)', 'entidade': 'Entidade'},
                     color='montante_divida',
                     color_continuous_scale='Reds')
        fig1.update_layout(height=400)
        graficos['divida_entidade'] = json.dumps(fig1, cls=PlotlyJSONEncoder)

        # 2. Gráfico de pizza - Dívida por Tipo de Produto
        df_produtos = df.groupby('produto')['montante_divida'].sum().reset_index()
        fig2 = px.pie(df_produtos, 
                     values='montante_divida', 
                     names='produto',
                     title='Distribuição da Dívida por Tipo de Produto',
                     hole=0.4,
                     color_discrete_sequence=px.colors.sequential.RdBu)
        fig2.update_layout(height=400)
        graficos['divida_produto'] = json.dumps(fig2, cls=PlotlyJSONEncoder)

        # 3. Gráfico de gauge - Taxa de Esforço
        fig3 = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=metricas['taxa_esforco'],
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Taxa de Esforço (%)", 'font': {'size': 24}},
            delta={'reference': 30, 'increasing': {'color': "#dc3545"}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1},
                'bar': {'color': metricas['cor_classificacao']},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 30], 'color': '#d4edda'},
                    {'range': [30, 40], 'color': '#fff3cd'},
                    {'range': [40, 60], 'color': '#f8d7da'},
                    {'range': [60, 100], 'color': '#721c24'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 40
                }
            }
        ))
        fig3.update_layout(height=350)
        graficos['gauge_esforco'] = json.dumps(fig3, cls=PlotlyJSONEncoder)

        # 4. Gráfico de barras - Prestações Mensais
        df_ativos = df[df['situacao'] != 'Liquidado'].copy()
        if not df_ativos.empty:
            fig4 = px.bar(df_ativos,
                         x='entidade',
                         y='prestacao_mensal',
                         color='situacao',
                         title='Prestações Mensais por Entidade',
                         labels={'prestacao_mensal': 'Prestação (€)', 'entidade': 'Entidade'},
                         color_discrete_map={'Regular': '#28a745', 'Incumprimento': '#dc3545'})
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
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        try:
            analyzer = CRCAnalyzer()
            dados = analyzer.extrair_dados_pdf(filepath)

            # Se não extraiu créditos, criar dados de demonstração
            if not dados['creditos']:
                dados['creditos'] = gerar_dados_demo()
                dados['demo_mode'] = True
            else:
                dados['demo_mode'] = False

            metricas = analyzer.calcular_metricas(dados['creditos'], rendimento)
            recomendacoes = analyzer.gerar_recomendacoes(dados['creditos'], metricas)
            graficos = analyzer.criar_graficos(dados['creditos'], metricas)

            # Preparar dados para JSON
            for c in dados['creditos']:
                for key, val in c.items():
                    if isinstance(val, float):
                        c[key] = round(val, 2)

            response = {
                'success': True,
                'titular': dados['titular'],
                'data_consulta': dados['data_consulta'],
                'demo_mode': dados.get('demo_mode', False),
                'creditos': dados['creditos'],
                'metricas': metricas,
                'recomendacoes': recomendacoes,
                'graficos': graficos,
                'resumo': {
                    'total_creditos': len(dados['creditos']),
                    'total_divida': sum(c['montante_divida'] for c in dados['creditos']),
                    'total_prestacoes': sum(c['prestacao_mensal'] for c in dados['creditos'] if c['situacao'] != 'Liquidado'),
                    'n_incumprimentos': len([c for c in dados['creditos'] if c['situacao'] == 'Incumprimento'])
                }
            }

            # Limpar arquivo
            os.remove(filepath)

            return jsonify(response)

        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Erro ao processar PDF: {str(e)}'}), 500

    return jsonify({'error': 'Formato de arquivo inválido. Use PDF.'}), 400


def gerar_dados_demo():
    """Gera dados de demonstração para teste"""
    return [
        {
            'entidade': 'Banco Santander Totta',
            'produto': 'Crédito Habitação',
            'tipo_negociacao': 'HAB-2020-001',
            'data_inicio': '15/03/2020',
            'data_fim': '15/03/2050',
            'montante_inicial': 150000.0,
            'montante_divida': 135420.50,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 580.25,
            'taxa_juro': 1.25,
            'prazo_total': 360,
            'prazo_restante': 324,
            'situacao': 'Regular',
            'garantias': ['Hipoteca'],
            'fiadores': []
        },
        {
            'entidade': 'Caixa Geral de Depósitos',
            'produto': 'Crédito Automóvel',
            'tipo_negociacao': 'AUT-2022-045',
            'data_inicio': '10/06/2022',
            'data_fim': '10/06/2027',
            'montante_inicial': 25000.0,
            'montante_divida': 18500.00,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 420.00,
            'taxa_juro': 5.99,
            'prazo_total': 60,
            'prazo_restante': 42,
            'situacao': 'Regular',
            'garantias': ['Penhor do veículo'],
            'fiadores': []
        },
        {
            'entidade': 'Millennium BCP',
            'produto': 'Cartão de Crédito',
            'tipo_negociacao': 'CC-2021-123',
            'data_inicio': '01/01/2021',
            'data_fim': '',
            'montante_inicial': 5000.0,
            'montante_divida': 3200.00,
            'montante_vencido': 450.00,
            'montante_abatido': 0.0,
            'prestacao_mensal': 150.00,
            'taxa_juro': 18.99,
            'prazo_total': 0,
            'prazo_restante': 0,
            'situacao': 'Incumprimento',
            'garantias': [],
            'fiadores': []
        },
        {
            'entidade': 'Novo Banco',
            'produto': 'Crédito Pessoal',
            'tipo_negociacao': 'CP-2023-089',
            'data_inicio': '20/09/2023',
            'data_fim': '20/09/2028',
            'montante_inicial': 15000.0,
            'montante_divida': 12800.00,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 285.50,
            'taxa_juro': 8.50,
            'prazo_total': 60,
            'prazo_restante': 48,
            'situacao': 'Regular',
            'garantias': [],
            'fiadores': ['Maria Silva']
        },
        {
            'entidade': 'Banco Santander Totta',
            'produto': 'Cartão de Crédito',
            'tipo_negociacao': 'CC-2019-567',
            'data_inicio': '05/12/2019',
            'data_fim': '',
            'montante_inicial': 3000.0,
            'montante_divida': 0.0,
            'montante_vencido': 0.0,
            'montante_abatido': 0.0,
            'prestacao_mensal': 0.0,
            'taxa_juro': 19.50,
            'prazo_total': 0,
            'prazo_restante': 0,
            'situacao': 'Liquidado',
            'garantias': [],
            'fiadores': []
        }
    ]


if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
