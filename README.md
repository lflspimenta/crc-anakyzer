# CRC Analyzer - Analise de Mapa de Responsabilidades de Credito

Aplicacao web para analise automatica do Mapa de Responsabilidades de Credito (CRC) do Banco de Portugal.

## Instalacao Rapida

### Windows (Automatico)
1. Extraia o projeto para uma pasta
2. Clique duas vezes em `install.bat`
3. Aguarde a instalacao (2-5 minutos)
4. Clique duas vezes em `start_app.bat`
5. Abra http://localhost:5000 no navegador

Para mais detalhes, veja [INSTALACAO_WINDOWS.md](INSTALACAO_WINDOWS.md).

### Linux/macOS (Manual)
```bash
# 1. Instalar prerequisitos do sistema
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-por poppler-utils

# macOS:
brew install tesseract poppler

# 2. Criar ambiente virtual
cd crc_analyzer
python -m venv venv

# 3. Ativar ambiente
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate   # Windows

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. Executar
python app.py

# 6. Abrir http://localhost:5000
```

## Funcionalidades

- **Upload de PDF** do CRC obtido em bportugal.pt (arrastar ou procurar)
- **Extracao automatica** de dados via OCR e parsing de PDF
- **Calculo de metricas financeiras**:
  - Taxa de esforco
  - Endividamento total
  - Racio de incumprimento
  - Score de saude financeira (0-100)
- **Dashboard interativo** com 4 graficos Plotly
- **Recomendacoes personalizadas** baseadas na situacao financeira
- **Simulador** com rendimento mensal ajustavel

## Estrutura do Projeto

```
crc_analyzer/
├── app.py                  # Aplicacao Flask principal
├── requirements.txt        # Dependencias Python
├── install.bat            # Instalador automatico (Windows)
├── start_app.bat          # Iniciar aplicacao (Windows)
├── INSTALACAO_WINDOWS.md  # Guia detalhado Windows
├── templates/
│   └── index.html         # Interface web
├── static/
│   └── js/
│       └── app.js         # Logica frontend
└── uploads/               # Pasta temporaria para uploads
```

## Metricas Calculadas

| Metrica | Descricao | Limite Recomendado |
|---------|-----------|-------------------|
| Taxa de Esforco | Total prestacoes / rendimento liquido | Max. 30-35% |
| Endividamento Anual | Divida total / rendimento anual | Alerta se > 3x |
| Score | Pontuacao global de saude financeira | > 60 |
| Incumprimentos | N de creditos em default | 0 |

## Notas Legais

- A app nao acede diretamente aos dados do Banco de Portugal
- O utilizador deve obter o PDF do CRC atraves do portal oficial
- A analise e meramente informativa e nao substitui aconselhamento financeiro profissional
- Nenhum dado e armazenado em servidores - processamento local

## Licenca

MIT License
