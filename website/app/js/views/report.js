/**
 * Report View — 4-module insight report visualization with Chart.js trend charts.
 */
const ReportView = (() => {
  let chartInstances = [];
  let currentReport = null;

  async function render(params) {
    const jobId = params.jobId;
    if (!jobId) {
      return `<div class="empty-state"><div class="empty-icon">📋</div><h3>未选择任务</h3><p>请先上传 CSV 文件进行分析</p></div>`;
    }

    return `
      <div class="view report-view">
        <div class="view-header">
          <div class="view-header-row">
            <div>
              <h1>📊 洞察报告</h1>
              <p>任务 ID: <code>${jobId}</code></p>
            </div>
            <div class="header-actions">
              <button class="btn btn-outline" id="btn-ask-jump">💬 追问分析</button>
              <button class="btn btn-outline" id="btn-hitl-jump">🔍 人工复核</button>
              <button class="btn btn-outline" id="btn-refresh-report">🔄 刷新</button>
            </div>
          </div>
        </div>
        <div id="report-content">
          <div class="loading-spinner"><div class="spinner"></div><p>加载报告中...</p></div>
        </div>
      </div>
    `;
  }

  async function mount(params) {
    const jobId = params.jobId;
    const container = document.getElementById('report-content');
    if (!container) return;

    // Bind header buttons
    ['btn-ask-jump', 'btn-hitl-jump', 'btn-refresh-report'].forEach(id => {
      const btn = document.getElementById(id);
      if (!btn) return;
      if (id === 'btn-ask-jump') btn.addEventListener('click', () => Router.navigate('/ask/' + jobId));
      if (id === 'btn-hitl-jump') btn.addEventListener('click', () => Router.navigate('/hitl/' + jobId));
      if (id === 'btn-refresh-report') btn.addEventListener('click', () => loadReport(jobId, container));
    });

    await loadReport(jobId, container);
  }

  async function loadReport(jobId, container) {
    try {
      const report = await API.getReport(jobId);
      currentReport = report;
      container.innerHTML = buildReportHTML(report, jobId);

      // Mount dashboard with three review pools
      Dashboard.mount(jobId);

      // Render trend chart after DOM update
      requestAnimationFrame(() => {
        renderTrendChart(report.trend_anomaly);
        renderSentimentPieChart(report);
      });
    } catch (err) {
      // Try getting status to give better error
      try {
        const status = await API.getJobStatus(jobId);
        if (status.status === 'running' || status.status === 'pending') {
          container.innerHTML = `
            <div id="dashboard"></div>
            <div class="empty-state" style="padding:2rem 0;">
              <div class="spinner"></div>
              <h3>分析进行中</h3>
              <p>当前状态: ${status.status === 'running' ? '正在分析中...' : '等待启动...'}</p>
              <button class="btn btn-primary mt-3" id="btn-poll-refresh">刷新状态</button>
            </div>`;
          Dashboard.mount(jobId);
          document.getElementById('btn-poll-refresh')?.addEventListener('click', () => loadReport(jobId, container));
          startPolling(jobId, container);
          return;
        }
        if (status.status === 'failed') {
          container.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><h3>分析失败</h3><p>${status.error || '未知错误'}</p></div>`;
          return;
        }
      } catch (_) {}
      container.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><h3>报告不可用</h3><p>${err.message}</p></div>`;
    }
  }

  function startPolling(jobId, container) {
    const interval = setInterval(async () => {
      try {
        const status = await API.getJobStatus(jobId);
        if (status.status === 'completed') {
          clearInterval(interval);
          await loadReport(jobId, container);
        } else if (status.status === 'failed') {
          clearInterval(interval);
          container.innerHTML = `<div class="empty-state"><div class="empty-icon">❌</div><h3>分析失败</h3><p>${status.error || '未知错误'}</p></div>`;
        }
      } catch (_) {}
    }, 3000);
  }

  function buildReportHTML(report, jobId) {
    const exec = report.executive_summary || {};
    const pain = report.pain_points || {};
    const trend = report.trend_anomaly || {};
    const recs = report.recommendations || [];

    return `
      <!-- Pipeline Dashboard: 三池指标 -->
      <div id="dashboard"></div>

      <!-- Module 1: Executive Summary -->
      <div class="report-module" id="mod-exec">
        <div class="module-header">
          <h2>📋 结论摘要</h2>
          <span class="module-tag">Executive Summary</span>
        </div>
        <div class="module-body">
          <div class="health-score-row">
            <div class="health-card">
              <div class="health-circle" style="--pct: ${exec.health_score || 0}">
                <div class="health-value">${(exec.health_score || 0).toFixed(1)}%</div>
                <div class="health-label">整体好评率</div>
              </div>
            </div>
            <div class="health-details">
              ${exec.health_trend ? `<div class="detail-item"><span class="detail-label">📈 趋势</span><span>${exec.health_trend}</span></div>` : ''}
              ${exec.highlights && exec.highlights.length > 0 ? `
                <div class="detail-item">
                  <span class="detail-label">✨ 亮点</span>
                  <ul class="detail-list">${exec.highlights.map(h => `<li>${h}</li>`).join('')}</ul>
                </div>` : ''}
              ${exec.red_alerts && exec.red_alerts.length > 0 ? `
                <div class="detail-item alert">
                  <span class="detail-label">🚨 警报</span>
                  <ul class="detail-list">${exec.red_alerts.map(a => `<li class="text-red">${a}</li>`).join('')}</ul>
                </div>` : ''}
            </div>
          </div>

          <!-- Sentiment distribution pie chart -->
          <div class="chart-row mt-4">
            <div class="chart-box" id="sentiment-pie-container">
              <h4>情感分布</h4>
              <canvas id="sentiment-pie-chart"></canvas>
            </div>
          </div>

          ${report.input_summary ? `<p class="input-summary">📌 ${report.input_summary}</p>` : ''}
        </div>
      </div>

      <!-- Module 2: Pain Points -->
      <div class="report-module" id="mod-pain">
        <div class="module-header">
          <h2>🔴 槽点分析</h2>
          <span class="module-tag">Pain Points</span>
        </div>
        <div class="module-body">
          ${pain.top_pain_points && pain.top_pain_points.length > 0 ? `
            <div class="pain-grid">
              ${pain.top_pain_points.map((pp, i) => `
                <div class="pain-card">
                  <div class="pain-rank">#${i + 1}</div>
                  <div class="pain-content">
                    <div class="pain-header">
                      <span class="tg tg-red">${pp.category}</span>
                      <span class="pain-stat">${pp.count} 次提及 (${(pp.percentage || 0).toFixed(1)}%)</span>
                    </div>
                    ${pp.top_sku ? `<div class="pain-meta">📦 最集中 SKU: <strong>${pp.top_sku}</strong></div>` : ''}
                    ${pp.top_user_segment ? `<div class="pain-meta">👤 最集中用户群: <strong>${pp.top_user_segment}</strong></div>` : ''}
                    ${pp.typical_voc && pp.typical_voc.length > 0 ? `
                      <div class="pain-voc">
                        <div class="voc-title">💬 用户原声</div>
                        ${pp.typical_voc.map(v => `<blockquote>"${escapeHTML(v)}"</blockquote>`).join('')}
                      </div>` : ''}
                  </div>
                </div>
              `).join('')}
            </div>` : '<p class="text-muted">暂无槽点数据</p>'}
          ${pain.cross_dimension_insights && pain.cross_dimension_insights.length > 0 ? `
            <div class="cross-insights mt-4">
              <h4>🔬 交叉维度洞察</h4>
              <ul>${pain.cross_dimension_insights.map(i => `<li>${i}</li>`).join('')}</ul>
            </div>` : ''}
        </div>
      </div>

      <!-- Module 3: Trend & Anomaly -->
      <div class="report-module" id="mod-trend">
        <div class="module-header">
          <h2>📈 趋势监控</h2>
          <span class="module-tag">Trend & Anomaly</span>
        </div>
        <div class="module-body">
          <div class="chart-container">
            <canvas id="trend-chart"></canvas>
          </div>
          ${trend.spike_alerts && trend.spike_alerts.length > 0 ? `
            <div class="spike-alerts mt-4">
              <h4>⚠️ 异常突增告警</h4>
              ${trend.spike_alerts.map(a => `
                <div class="spike-card severity-${(a.severity || 'WARNING').toLowerCase()}">
                  <div class="spike-severity">${a.severity === 'CRITICAL' ? '🔴' : '🟡'} ${a.severity}</div>
                  <div class="spike-body">
                    <strong>${escapeHTML(a.issue || '')}</strong>
                    <div class="spike-metrics">
                      <span>历史占比: ${(a.historical_ratio || 0).toFixed(1)}%</span>
                      <span>→</span>
                      <span class="text-red">当前占比: ${(a.current_ratio || 0).toFixed(1)}%</span>
                    </div>
                  </div>
                </div>
              `).join('')}
            </div>
          ` : '<p class="text-muted mt-3">✅ 未检测到异常突增</p>'}
        </div>
      </div>

      <!-- Module 4: Recommendations -->
      <div class="report-module" id="mod-rec">
        <div class="module-header">
          <h2>💡 改进建议</h2>
          <span class="module-tag">Recommendations</span>
        </div>
        <div class="module-body">
          ${recs.length > 0 ? `
            <div class="rec-list">
              ${recs.map(r => `
                <div class="rec-card priority-${r.priority}">
                  <div class="rec-priority">
                    <span class="priority-badge p${r.priority}">P${r.priority}</span>
                  </div>
                  <div class="rec-content">
                    <div class="rec-header">
                      <span class="tg tg-gray">${escapeHTML(r.category || '')}</span>
                    </div>
                    <p class="rec-suggestion">${escapeHTML(r.suggestion || '')}</p>
                    ${r.evidence ? `<p class="rec-evidence">📊 ${escapeHTML(r.evidence)}</p>` : ''}
                  </div>
                </div>
              `).join('')}
            </div>` : '<p class="text-muted">暂无改进建议</p>'}
        </div>
      </div>`;
  }

  // ---- Chart Rendering ----

  function renderTrendChart(trendData) {
    const canvas = document.getElementById('trend-chart');
    if (!canvas || !trendData || !trendData.trend_data || !trendData.trend_data.length) {
      if (canvas) {
        const ctx = canvas.getContext('2d');
        ctx.font = '14px sans-serif';
        ctx.fillStyle = '#9ca3af';
        ctx.textAlign = 'center';
        ctx.fillText('暂无趋势数据', canvas.width / 2, canvas.height / 2);
      }
      return;
    }

    const data = trendData.trend_data;
    const labels = data.map(d => d.date || '');
    const posData = data.map(d => d.positive_count || 0);
    const negData = data.map(d => d.negative_count || 0);
    const neuData = data.map(d => d.neutral_count || 0);

    // Destroy existing chart instance on this canvas
    const existingChart = Chart.getChart(canvas);
    if (existingChart) existingChart.destroy();

    const chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: '正面',
            data: posData,
            borderColor: '#059669',
            backgroundColor: 'rgba(5, 150, 105, 0.08)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: '负面',
            data: negData,
            borderColor: '#dc2626',
            backgroundColor: 'rgba(220, 38, 38, 0.08)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
          {
            label: '中性',
            data: neuData,
            borderColor: '#9ca3af',
            backgroundColor: 'rgba(156, 163, 175, 0.08)',
            fill: true,
            tension: 0.3,
            pointRadius: 3,
            pointHoverRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, padding: 20, font: { size: 12 } } },
          tooltip: { backgroundColor: '#fff', titleColor: '#111827', bodyColor: '#4b5563', borderColor: '#e5e7eb', borderWidth: 1, cornerRadius: 8, padding: 12 },
        },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 11 }, color: '#9ca3af' } },
          y: { grid: { color: '#f3f4f6' }, ticks: { font: { size: 11 }, color: '#9ca3af' }, beginAtZero: true },
        },
      },
    });
    chartInstances.push(chart);
  }

  function renderSentimentPieChart(report) {
    const canvas = document.getElementById('sentiment-pie-chart');
    if (!canvas) return;

    // Try to derive sentiment counts from available data
    const exec = report.executive_summary || {};
    const healthScore = exec.health_score || 0;

    // If we don't have detailed counts, show a simplified health view
    const posPct = healthScore;
    const negPct = 100 - healthScore;

    const existingChart = Chart.getChart(canvas);
    if (existingChart) existingChart.destroy();

    const chart = new Chart(canvas, {
      type: 'doughnut',
      data: {
        labels: ['好评', '差评/中性'],
        datasets: [{
          data: [posPct, negPct],
          backgroundColor: ['#059669', '#e5e7eb'],
          borderColor: '#fff',
          borderWidth: 2,
          hoverBorderColor: '#fff',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '65%',
        plugins: {
          legend: { position: 'bottom', labels: { usePointStyle: true, padding: 16, font: { size: 12 } } },
          tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${ctx.raw.toFixed(1)}%` } },
        },
      },
    });
    chartInstances.push(chart);
  }

  // ---- Utilities ----

  function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function destroy() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
    currentReport = null;
  }

  return { render, mount, destroy };
})();
