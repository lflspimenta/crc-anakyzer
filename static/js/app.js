
document.addEventListener('DOMContentLoaded', function() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const fileName = document.getElementById('fileName');
    const btnAnalyze = document.getElementById('btnAnalyze');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const resultsSection = document.getElementById('resultsSection');

    let selectedFile = null;

    // Upload area events
    uploadArea.addEventListener('click', () => fileInput.click());

    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');

        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type === 'application/pdf') {
            handleFile(files[0]);
        } else {
            alert('Por favor, envie apenas arquivos PDF.');
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFile(e.target.files[0]);
        }
    });

    // Botão "Procurar no computador"
    const btnBrowse = document.getElementById('btnBrowse');
    if (btnBrowse) {
        btnBrowse.addEventListener('click', (e) => {
            e.stopPropagation(); // Evitar que o clique propague para a uploadArea
            fileInput.click();
        });
    }

    function handleFile(file) {
        selectedFile = file;

        // Mostrar info do ficheiro
        const fileInfo = document.getElementById('fileInfo');
        const fileSize = document.getElementById('fileSize');

        if (fileName) fileName.textContent = file.name;
        if (fileSize) {
            const size = file.size;
            if (size < 1024) {
                fileSize.textContent = size + ' bytes';
            } else if (size < 1024 * 1024) {
                fileSize.textContent = (size / 1024).toFixed(1) + ' KB';
            } else {
                fileSize.textContent = (size / (1024 * 1024)).toFixed(1) + ' MB';
            }
        }
        if (fileInfo) fileInfo.classList.add('active');

        // Atualizar visual da área de upload
        const uploadArea = document.getElementById('uploadArea');
        if (uploadArea) {
            uploadArea.style.borderColor = 'var(--success-color)';
            uploadArea.style.background = '#f0fff4';
        }

        btnAnalyze.disabled = false;
    }

    // Analyze button
    btnAnalyze.addEventListener('click', async () => {
        if (!selectedFile) return;

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('rendimento', document.getElementById('rendimentoInput').value);

        loadingOverlay.classList.add('active');

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                displayResults(data);
            } else {
                alert('Erro: ' + data.error);
            }
        } catch (error) {
            alert('Erro ao processar: ' + error.message);
        } finally {
            loadingOverlay.classList.remove('active');
        }
    });

    function displayResults(data) {
        resultsSection.classList.add('active');

        // Demo mode alert
        const demoAlert = document.getElementById('demoAlert');
        if (data.demo_mode) {
            demoAlert.style.display = 'block';
        } else {
            demoAlert.style.display = 'none';
        }

        // Header info
        document.getElementById('titularName').textContent = data.titular || 'Titular não identificado';
        document.getElementById('dataConsulta').textContent = 'Consulta em: ' + (data.data_consulta || 'Data não identificada');

        // Score
        const score = data.metricas.score;
        const scoreCircle = document.getElementById('scoreCircle');
        const scoreValue = document.getElementById('scoreValue');
        const scoreLabel = document.getElementById('scoreLabel');
        const scoreDesc = document.getElementById('scoreDesc');

        scoreValue.textContent = score;
        scoreCircle.style.background = data.metricas.cor_classificacao;
        scoreLabel.textContent = data.metricas.classificacao;

        const descricoes = {
            'Excelente': 'Situação financeira excelente. Tem capacidade para novos créditos e pode considerar investimentos.',
            'Bom': 'Situação financeira estável. Pode solicitar novos créditos com boas condições.',
            'Atenção': 'Situação requer atenção. Avalie a renegociação de créditos existentes.',
            'Risco': 'Situação de risco. Priorize a regularização de dívidas e redução de compromissos.',
            'Crítico': 'Situação crítica. Procure ajuda profissional urgentemente para reestruturar dívidas.'
        };
        scoreDesc.textContent = descricoes[data.metricas.classificacao] || '';

        // Metrics
        document.getElementById('metricDivida').textContent = formatCurrency(data.metricas.total_divida);
        document.getElementById('metricPrestacoes').textContent = formatCurrency(data.metricas.total_prestacoes);
        document.getElementById('metricEsforco').textContent = data.metricas.taxa_esforco + '%';
        document.getElementById('metricCreditos').textContent = data.metricas.n_creditos_ativos;
        document.getElementById('metricIncumprimentos').textContent = data.metricas.n_incumprimentos;
        document.getElementById('metricEndividamento').textContent = data.metricas.endividamento_anual + 'x';
        document.getElementById('metricVencido').textContent = formatCurrency(data.metricas.total_vencido);
        document.getElementById('metricAbatido').textContent = formatCurrency(data.metricas.total_abatido);

        // Charts
        if (data.graficos.divida_produto) {
            Plotly.newPlot('chartProduto', JSON.parse(data.graficos.divida_produto).data, 
                          JSON.parse(data.graficos.divida_produto).layout, {responsive: true});
        }
        if (data.graficos.divida_entidade) {
            Plotly.newPlot('chartEntidade', JSON.parse(data.graficos.divida_entidade).data,
                          JSON.parse(data.graficos.divida_entidade).layout, {responsive: true});
        }
        if (data.graficos.gauge_esforco) {
            Plotly.newPlot('chartGauge', JSON.parse(data.graficos.gauge_esforco).data,
                          JSON.parse(data.graficos.gauge_esforco).layout, {responsive: true});
        }
        if (data.graficos.prestacoes) {
            Plotly.newPlot('chartPrestacoes', JSON.parse(data.graficos.prestacoes).data,
                          JSON.parse(data.graficos.prestacoes).layout, {responsive: true});
        }
        if (data.graficos.timeline) {
            Plotly.newPlot('chartTimeline', JSON.parse(data.graficos.timeline).data,
                          JSON.parse(data.graficos.timeline).layout, {responsive: true});
        }

        // Recommendations
        const recContainer = document.getElementById('recommendationsContainer');
        recContainer.innerHTML = '';

        data.recomendacoes.forEach(rec => {
            const card = document.createElement('div');
            card.className = `recommendation-card ${rec.tipo}`;

            const icons = {
                'urgente': 'fa-exclamation-circle',
                'alerta': 'fa-exclamation-triangle',
                'info': 'fa-info-circle',
                'sucesso': 'fa-check-circle'
            };

            card.innerHTML = `
                <div class="rec-title">
                    <i class="fas ${icons[rec.tipo] || 'fa-info-circle'}"></i>
                    ${rec.titulo}
                </div>
                <div class="rec-desc">${rec.descricao}</div>
                <span class="rec-action">${rec.acao}</span>
                <span class="rec-impact"><i class="fas fa-arrow-up"></i> ${rec.impacto}</span>
            `;
            recContainer.appendChild(card);
        });

        // Creditos table
        const tbody = document.getElementById('creditosTableBody');
        tbody.innerHTML = '';

        data.creditos.forEach(credito => {
            const row = document.createElement('tr');

            let badgeClass = 'badge-regular';
            if (credito.situacao === 'Incumprimento') badgeClass = 'badge-incumprimento';
            else if (credito.situacao === 'Liquidado') badgeClass = 'badge-liquidado';

            row.innerHTML = `
                <td><strong>${credito.entidade}</strong></td>
                <td>${credito.produto}</td>
                <td>${formatCurrency(credito.montante_inicial)}</td>
                <td class="fw-bold ${credito.montante_divida > 0 ? 'text-danger' : ''}">${formatCurrency(credito.montante_divida)}</td>
                <td>${formatCurrency(credito.prestacao_mensal)}</td>
                <td>${credito.taxa_juro > 0 ? credito.taxa_juro + '%' : '-'}</td>
                <td><span class="badge-situacao ${badgeClass}">${credito.situacao}</span></td>
                <td>${credito.garantias.join(', ') || '-'}</td>
            `;
            tbody.appendChild(row);
        });

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function formatCurrency(value) {
        if (value === undefined || value === null) return '-';
        return new Intl.NumberFormat('pt-PT', {
            style: 'currency',
            currency: 'EUR'
        }).format(value);
    }
});
