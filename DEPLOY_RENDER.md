# CRC Analyzer - Deploy na Web

## Opcao Recomendada: Render (Gratuito, Suporta Python)

O Netlify so suporta sites estaticos (HTML/CSS/JS). Como o CRC Analyzer usa Python/Flask no backend, precisas de um servico que suporte Python.

**Render** e a melhor opcao gratuita para Flask.

---

## Passo a Passo: Deploy no Render

### 1. Preparar o projeto (ja feito)

Os seguintes ficheiros ja estao configurados:
- `Procfile` - comando de arranque do servidor
- `runtime.txt` - versao do Python (3.11.8)
- `render.yaml` - configuracao Blueprint (opcional)
- `requirements.txt` - inclui gunicorn

### 2. Criar repositorio no GitHub

```bash
# Na pasta do projeto
git init
git add .
git commit -m "Primeiro commit - CRC Analyzer"
git branch -M main
git remote add origin https://github.com/TEU_USER/crc-analyzer.git
git push -u origin main
```

Substitui `TEU_USER` pelo teu username do GitHub.

### 3. Criar conta no Render

1. Vai a https://render.com
2. Clica em "Get Started for Free"
3. Regista-te com GitHub (recomendado)

### 4. Criar Web Service

1. No dashboard do Render, clica em **"New +"** (canto superior direito)
2. Seleciona **"Web Service"**
3. Conecta o repositorio `crc-analyzer` do GitHub
4. Configura:

| Campo | Valor |
|-------|-------|
| **Name** | crc-analyzer |
| **Region** | Frankfurt (EU) |
| **Runtime** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn app:app` |
| **Plan** | Free |

5. Clica em **"Create Web Service"**

### 5. Aguardar o deploy

O Render vai:
1. Instalar dependencias (`pip install`)
2. Fazer build
3. Iniciar o servidor Gunicorn

Demora ~2-5 minutos no primeiro deploy.

### 6. Aceder a aplicacao

Quando o status mudar para **"Live"**, clica no link gerado:
- Exemplo: `https://crc-analyzer.onrender.com`

---

## Atualizacoes Automaticas

Sempre que fizeres `git push` para o GitHub, o Render faz deploy automatico!

```bash
git add .
git commit -m "Nova funcionalidade"
git push origin main
```

---

## Limitacoes do Plano Gratis (Render)

| Limite | Detalhe |
|--------|---------|
| **Inatividade** | Servidor "dorme" apos 15 min sem uso |
| **Wake-up time** | ~30 segundos para acordar |
| **RAM** | 512 MB |
| **Disco** | Nao persistente (apaga no restart) |
| **CPU** | Partilhada |

Para a CRC Analyzer isto e suficiente porque nao guarda dados permanentemente.

---

## Outras Opcoes (Se Render nao funcionar)

### Railway (https://railway.app)
- Plano gratis: $5/mes de credito
- Suporta Python nativamente
- Deploy via GitHub

### PythonAnywhere (https://pythonanywhere.com)
- Plano gratis: muito limitado (CPU, memoria)
- Bom para prototipos
- Painel web simples

### VPS Pago (DigitalOcean, Linode, Hetzner)
- ~5 euros/mes
- Servidor dedicado
- Total controlo
- Requer configuracao manual (nginx, systemd, etc.)

---

## Porque nao Netlify?

| Caracteristica | Netlify | Render |
|----------------|---------|--------|
| Sites estaticos | ✅ Sim | ✅ Sim |
| Backend Python | ❌ Nao | ✅ Sim |
| Banco de dados | ❌ Nao | ✅ Sim |
| Plano gratis | ✅ Generoso | ✅ Suficiente |
| Custom domains | ✅ Sim | ✅ Sim |
| SSL automatico | ✅ Sim | ✅ Sim |

**Conclusao:** Usa Netlify para landing pages, blogs, portfolios. Usa Render para apps com backend Python.
