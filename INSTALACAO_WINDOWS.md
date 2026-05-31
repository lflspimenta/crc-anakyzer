
# Guia de Instalacao - CRC Analyzer (Windows)

## Problema: ModuleNotFoundError: No module named 'flask'

Este erro significa que as dependencias Python ainda nao estao instaladas.
Siga os passos abaixo para resolver.

---

## Metodo 1: Instalacao Automatica (Recomendado)

1. Abra a pasta do projeto no Explorador de Ficheiros
2. Clique duas vezes em `install.bat`
3. Aguarde a instalacao (pode demorar 2-5 minutos)
4. Quando terminar, clique duas vezes em `start_app.bat`
5. Abra o navegador em http://localhost:5000

---

## Metodo 2: Instalacao Manual (Linha de Comandos)

### Passo 1: Verificar Python
Abra o Prompt de Comandos (cmd) e execute:
```
python --version
```
Deve mostrar algo como `Python 3.11.x`. Se nao mostrar, instale Python em https://python.org (marque "Add Python to PATH" durante a instalacao).

### Passo 2: Navegar ate a pasta do projeto
```
cd C:\caminho\para\crc_analyzer
```

### Passo 3: Criar ambiente virtual (recomendado)
```
python -m venv venv
```

### Passo 4: Ativar ambiente virtual
```
venv\Scripts\activate
```
O prompt deve mudar para mostrar `(venv)` no inicio.

### Passo 5: Instalar dependencias
```
pip install -r requirements.txt
```

### Passo 6: Executar a aplicacao
```
python app.py
```

### Passo 7: Abrir no navegador
Va a http://localhost:5000

---

## Metodo 3: Instalacao Global (nao recomendado)

Se nao quiser usar ambiente virtual, instale diretamente:

```
pip install flask werkzeug pdfplumber pdf2image pytesseract pillow pandas plotly openpyxl numpy
```

Depois execute:
```
python app.py
```

---

## Prerequisitos do Sistema

### Tesseract OCR (opcional, mas recomendado)
Para extrair texto de PDFs digitalizados:
1. Descarregue em: https://github.com/UB-Mannheim/tesseract/wiki
2. Instale com suporte para portugues (por)
3. Adicione ao PATH do sistema

### Poppler (opcional)
Para conversao PDF -> imagem (OCR fallback):
1. Descarregue em: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extraia para uma pasta (ex: C:\poppler)
3. Adicione `C:\poppler\bin` ao PATH do sistema

**Nota:** Mesmo sem estes prerequisitos, a aplicacao funciona com dados de demonstracao.

---

## Erros Comuns

### "pip nao e reconhecido"
Solucao: Reinstale Python e marque "Add Python to PATH"

### "Nao e possivel ativar ambiente virtual"
Solucao: Execute no PowerShell como Administrador:
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### "Erro ao instalar pdfplumber"
Solucao: Atualize pip primeiro:
```
pip install --upgrade pip
pip install -r requirements.txt
```

### "Porta 5000 em uso"
Solucao: Edite app.py e mude a porta:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

---

## Verificacao Rapida

Depois de instalar, verifique se tudo esta correto:
```
python -c "import flask; print('Flask OK')"
python -c "import pdfplumber; print('pdfplumber OK')"
python -c "import pandas; print('pandas OK')"
python -c "import plotly; print('plotly OK')"
```

Se todos mostrarem "OK", a instalacao esta correta.
