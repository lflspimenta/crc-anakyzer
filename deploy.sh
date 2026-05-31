#!/bin/bash
# deploy.sh - Script para fazer deploy no Render via GitHub

echo "=========================================="
echo "   CRC Analyzer - Deploy para Render"
echo "=========================================="
echo ""

# Verificar se git esta instalado
if ! command -v git &> /dev/null; then
    echo "[ERRO] Git nao esta instalado."
    echo "Instale em: https://git-scm.com/downloads"
    exit 1
fi

# Verificar se existe repositorio
if [ ! -d .git ]; then
    echo "[INFO] Inicializando repositorio Git..."
    git init
    git branch -M main
    echo ""
    echo "Por favor, crie um repositorio no GitHub:"
    echo "  https://github.com/new"
    echo ""
    read -p "Introduza a URL do repositorio GitHub: " repo_url
    git remote add origin $repo_url
fi

echo "[1/3] A adicionar ficheiros..."
git add .

echo "[2/3] A fazer commit..."
git commit -m "Deploy v$(date +%Y%m%d-%H%M%S)"

echo "[3/3] A enviar para GitHub..."
git push -u origin main

echo ""
echo "=========================================="
echo "   Deploy enviado!"
echo "=========================================="
echo ""
echo "O Render vai detetar o push e fazer deploy automatico."
echo "Verifique o status em: https://dashboard.render.com"
echo ""
