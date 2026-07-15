/**
 * Samples View — Few-shot 样本库 + Golden 数据集浏览器
 */
const SamplesView = (() => {
  let activeTab = 'fewshot';
  let fewshotData = [];
  let goldenData = [];

  async function render() {
    return `
      <div class="view samples-view">
        <div class="view-header">
          <h1>🧪 样本库与数据集</h1>
          <p>Few-shot 样本库用于 Prompt 工程参考，Golden 数据集用于验证提取准确率</p>
        </div>

        <div class="samples-tabs">
          <button class="samples-tab active" data-tab="fewshot" id="tab-fewshot">
            📚 Few-shot 样本库 <span class="tab-count" id="fewshot-count"></span>
          </button>
          <button class="samples-tab" data-tab="golden" id="tab-golden">
            🏅 Golden 数据集 <span class="tab-count" id="golden-count"></span>
          </button>
        </div>

        <div id="samples-content">
          <div class="loading-spinner"><div class="spinner"></div><p>加载样本库...</p></div>
        </div>
      </div>
    `;
  }

  async function mount() {
    // Tab switching
    document.querySelectorAll('.samples-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.samples-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        activeTab = tab.dataset.tab;
        renderContent();
      });
    });

    // Load data
    await loadData();
    renderContent();
  }

  async function loadData() {
    try {
      const [fewshotRes, goldenRes] = await Promise.all([
        fetch('data/fewshot_library.json').then(r => r.json()),
        fetch('data/golden_dataset.json').then(r => r.json()),
      ]);
      fewshotData = fewshotRes;
      goldenData = goldenRes;
      document.getElementById('fewshot-count').textContent = `(${fewshotData.length} 条)`;
      document.getElementById('golden-count').textContent = `(${goldenData.length} 条)`;
    } catch (err) {
      document.getElementById('samples-content').innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>数据加载失败</h3>
          <p>${err.message}</p>
          <p class="text-muted">请确保已运行 <code>python3 data/generate_data.py</code></p>
        </div>`;
    }
  }

  function renderContent() {
    const container = document.getElementById('samples-content');
    if (!container) return;

    if (activeTab === 'fewshot') {
      container.innerHTML = renderFewshot();
      mountFewshotInteractions();
    } else {
      container.innerHTML = renderGolden();
      mountGoldenInteractions();
    }
  }

  // ================================================================
  // Few-shot 样本库
  // ================================================================

  function renderFewshot() {
    // Group by category
    const groups = {};
    fewshotData.forEach(fs => {
      const cat = fs.category || '其他';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(fs);
    });

    // Category metadata
    const catMeta = {
      '反讽识别': { icon: '🔄', desc: '表面用词与真实情感不一致的评论，需要 LLM 识别语气反转', color: 'red' },
      '无意义内容': { icon: '🗑️', desc: '纯数字/表情/默认评价，不包含可提取的有效信息', color: 'gray' },
      '明贬暗褒': { icon: '🎭', desc: '看似抱怨实则炫耀的评论，真实情感为正面', color: 'purple' },
      '混合情感': { icon: '⚖️', desc: '同时包含正面和负面评价，不能简单归为单一情感', color: 'amber' },
      '纯正面': { icon: '✅', desc: '标准好评，无歧义，置信度应高', color: 'green' },
      '纯负面': { icon: '❌', desc: '明确的多维度差评，直接提取即可', color: 'red' },
      '安全红线': { icon: '🚨', desc: '涉及安全/健康/欺诈的评论，标记为最高紧急度', color: 'red' },
      '价格争议': { icon: '💰', desc: '对价格变动/性价比的不满', color: 'amber' },
      '物流投诉': { icon: '📦', desc: '物流配送相关的负面体验', color: 'amber' },
      '客服投诉': { icon: '🎧', desc: '客服/售后服务质量投诉', color: 'amber' },
      '隐含好评': { icon: '👍', desc: '通过行为（回购/推荐）间接表达满意的评论', color: 'green' },
      '尺码问题': { icon: '📏', desc: '尺码偏差导致的负面体验', color: 'amber' },
      '中性评价': { icon: '➖', desc: '用户尚未形成明确判断的评论', color: 'gray' },
    };

    let html = '<div class="fewshot-overview">';
    html += '<div class="overview-cards">';
    for (const [cat, items] of Object.entries(groups)) {
      const meta = catMeta[cat] || { icon: '📝', desc: '', color: 'gray' };
      html += `
        <div class="overview-card oc-${meta.color}">
          <div class="oc-icon">${meta.icon}</div>
          <div class="oc-info">
            <div class="oc-name">${cat}</div>
            <div class="oc-count">${items.length} 条样本</div>
            <div class="oc-desc">${meta.desc}</div>
          </div>
        </div>`;
    }
    html += '</div></div>';

    // Detail cards
    html += '<div class="fewshot-list">';
    fewshotData.forEach((fs, idx) => {
      const diffLabel = { easy: '简单', medium: '中等', hard: '困难' }[fs.difficulty] || fs.difficulty;
      const diffClass = `diff-${fs.difficulty}`;
      const ext = fs.extraction || {};
      html += `
        <div class="fewshot-card" id="fs-${idx}">
          <div class="fs-header">
            <span class="fs-id">${fs.id}</span>
            <span class="tg tg-gray">${fs.category}</span>
            <span class="fs-difficulty ${diffClass}">${diffLabel}</span>
            <button class="btn btn-sm btn-outline fs-toggle" data-idx="${idx}">展开</button>
          </div>
          <div class="fs-review">
            <span class="fs-quote">"${escapeHTML(fs.review)}"</span>
          </div>
          <div class="fs-detail hidden" id="fs-detail-${idx}">
            <div class="fs-pattern">
              <span class="fs-label">识别模式</span>
              <span>${escapeHTML(fs.pattern || '')}</span>
            </div>
            <div class="fs-extraction">
              <div class="fs-extract-row">
                <span class="fs-label">情感</span><span class="tg tg-blue">${ext.sentiment}</span>
                <span class="fs-label">分类</span><span class="tg tg-green">${ext.primary_category}</span>
                <span class="fs-label">紧急度</span><span class="tg ${ext.urgency_level >= 3 ? 'tg-red' : ext.urgency_level >= 2 ? 'tg-amber' : 'tg-gray'}">P${ext.urgency_level}</span>
                <span class="fs-label">置信度</span><span>${((ext.confidence || 0) * 100).toFixed(0)}%</span>
              </div>
              <div class="fs-summary">
                <span class="fs-label">摘要</span>
                <code>${escapeHTML(ext.core_issue_summary || '')}</code>
              </div>
              <div class="fs-keywords">
                <span class="fs-label">关键词</span>
                ${(ext.extracted_keywords || []).map(k => `<span class="tg tg-purple">${escapeHTML(k)}</span>`).join(' ')}
              </div>
            </div>
            <div class="fs-notes">
              <span class="fs-label">💡 标注说明</span>
              <p>${escapeHTML(fs.notes || '')}</p>
            </div>
          </div>
        </div>`;
    });
    html += '</div>';
    return html;
  }

  function mountFewshotInteractions() {
    document.querySelectorAll('.fs-toggle').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = btn.dataset.idx;
        const detail = document.getElementById('fs-detail-' + idx);
        if (detail) {
          detail.classList.toggle('hidden');
          btn.textContent = detail.classList.contains('hidden') ? '展开' : '收起';
        }
      });
    });
  }

  // ================================================================
  // Golden 数据集
  // ================================================================

  function renderGolden() {
    const stats = computeGoldenStats();

    let html = `
      <div class="golden-stats">
        <div class="stat-card">
          <div class="stat-num">${goldenData.length}</div>
          <div class="stat-lbl">总样本数</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">${Object.keys(stats.sentiment).length}</div>
          <div class="stat-lbl">情感类别</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">${Object.keys(stats.category).length}</div>
          <div class="stat-lbl">问题分类</div>
        </div>
        <div class="stat-card">
          <div class="stat-num">3</div>
          <div class="stat-lbl">紧急度级别</div>
        </div>
      </div>

      <div class="golden-distributions">
        <div class="dist-card">
          <h4>情感分布</h4>
          <div class="dist-bars">
            ${renderDistBars(stats.sentiment, { '正面': 'green', '负面': 'red', '混合': 'amber', '中性': 'gray' })}
          </div>
        </div>
        <div class="dist-card">
          <h4>分类分布</h4>
          <div class="dist-bars">
            ${renderDistBars(stats.category, { '产品质量': 'red', '物流配送': 'amber', '服务态度': 'purple', '价格争议': 'amber', '无效评论': 'gray' })}
          </div>
        </div>
        <div class="dist-card">
          <h4>紧急度分布</h4>
          <div class="dist-bars">
            ${renderDistBars(stats.urgency, { '1': 'green', '2': 'amber', '3': 'red' }, true)}
          </div>
        </div>
      </div>

      <div class="golden-controls">
        <div class="golden-filters">
          <select id="filter-sentiment" class="golden-filter">
            <option value="">全部情感</option>
            ${Object.keys(stats.sentiment).map(s => `<option value="${s}">${s}</option>`).join('')}
          </select>
          <select id="filter-category" class="golden-filter">
            <option value="">全部分类</option>
            ${Object.keys(stats.category).map(c => `<option value="${c}">${c}</option>`).join('')}
          </select>
          <select id="filter-urgency" class="golden-filter">
            <option value="">全部紧急度</option>
            ${Object.keys(stats.urgency).map(u => `<option value="${u}">P${u}</option>`).join('')}
          </select>
          <input type="text" id="filter-search" class="golden-filter golden-search" placeholder="搜索评论内容...">
        </div>
        <span class="golden-showing" id="golden-showing"></span>
      </div>

      <div class="golden-table-wrap">
        <table class="golden-table" id="golden-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>评论内容</th>
              <th>预期情感</th>
              <th>预期分类</th>
              <th>紧急度</th>
              <th>标注说明</th>
            </tr>
          </thead>
          <tbody id="golden-tbody"></tbody>
        </table>
      </div>
      <div class="golden-pagination" id="golden-pagination"></div>
    `;
    return html;
  }

  function mountGoldenInteractions() {
    let filtered = [...goldenData];
    const pageSize = 30;
    let page = 0;

    function applyFilters() {
      const s = document.getElementById('filter-sentiment')?.value || '';
      const c = document.getElementById('filter-category')?.value || '';
      const u = document.getElementById('filter-urgency')?.value || '';
      const q = (document.getElementById('filter-search')?.value || '').toLowerCase();

      filtered = goldenData.filter(g => {
        if (s && g.expected_sentiment !== s) return false;
        if (c && g.expected_category !== c) return false;
        if (u && String(g.expected_urgency) !== u) return false;
        if (q && !g.review_content.toLowerCase().includes(q)) return false;
        return true;
      });
      page = 0;
      renderGoldenTable(filtered, page, pageSize);
    }

    document.getElementById('filter-sentiment')?.addEventListener('change', applyFilters);
    document.getElementById('filter-category')?.addEventListener('change', applyFilters);
    document.getElementById('filter-urgency')?.addEventListener('change', applyFilters);
    document.getElementById('filter-search')?.addEventListener('input', debounce(applyFilters, 300));

    renderGoldenTable(filtered, page, pageSize);
  }

  function renderGoldenTable(data, page, pageSize) {
    const tbody = document.getElementById('golden-tbody');
    const showing = document.getElementById('golden-showing');
    const pagination = document.getElementById('golden-pagination');
    if (!tbody) return;

    const totalPages = Math.ceil(data.length / pageSize);
    const start = page * pageSize;
    const slice = data.slice(start, start + pageSize);

    const sentColors = { '正面': 'tg-green', '负面': 'tg-red', '中性': 'tg-gray', '混合': 'tg-amber' };
    const urgColors = { 1: 'tg-green', 2: 'tg-amber', 3: 'tg-red' };

    tbody.innerHTML = slice.map(g => `
      <tr>
        <td><code>${g.review_id}</code></td>
        <td class="golden-content">${escapeHTML(g.review_content)}</td>
        <td><span class="tg ${sentColors[g.expected_sentiment] || 'tg-gray'}">${g.expected_sentiment}</span></td>
        <td><span class="tg tg-gray">${g.expected_category}</span></td>
        <td><span class="tg ${urgColors[g.expected_urgency] || 'tg-gray'}">P${g.expected_urgency}</span></td>
        <td class="golden-note">${escapeHTML(g.note || '')}</td>
      </tr>
    `).join('');

    showing.textContent = `显示 ${start + 1}-${Math.min(start + pageSize, data.length)} / 共 ${data.length} 条`;

    pagination.innerHTML = `
      <button class="btn btn-sm btn-outline" ${page === 0 ? 'disabled' : ''} id="btn-prev">上一页</button>
      <span class="page-info">${page + 1} / ${totalPages || 1}</span>
      <button class="btn btn-sm btn-outline" ${page >= totalPages - 1 ? 'disabled' : ''} id="btn-next">下一页</button>
    `;

    document.getElementById('btn-prev')?.addEventListener('click', () => {
      if (page > 0) { page--; renderGoldenTable(data, page, pageSize); window.scrollTo({ top: 400, behavior: 'smooth' }); }
    });
    document.getElementById('btn-next')?.addEventListener('click', () => {
      if (page < totalPages - 1) { page++; renderGoldenTable(data, page, pageSize); window.scrollTo({ top: 400, behavior: 'smooth' }); }
    });
  }

  // ================================================================
  // Utilities
  // ================================================================

  function computeGoldenStats() {
    const sentiment = {}, category = {}, urgency = {};
    goldenData.forEach(g => {
      sentiment[g.expected_sentiment] = (sentiment[g.expected_sentiment] || 0) + 1;
      category[g.expected_category] = (category[g.expected_category] || 0) + 1;
      urgency[g.expected_urgency] = (urgency[g.expected_urgency] || 0) + 1;
    });
    return { sentiment, category, urgency };
  }

  function renderDistBars(dist, colors, isUrgency = false) {
    const total = Object.values(dist).reduce((a, b) => a + b, 0);
    return Object.entries(dist)
      .sort((a, b) => b[1] - a[1])
      .map(([key, count]) => {
        const pct = ((count / total) * 100).toFixed(1);
        const color = colors[key] || 'gray';
        const label = isUrgency ? `P${key}` : key;
        return `
          <div class="dist-bar">
            <span class="dist-label">${label}</span>
            <div class="dist-track">
              <div class="dist-fill fill-${color}" style="width:${pct}%"></div>
            </div>
            <span class="dist-val">${count} (${pct}%)</span>
          </div>`;
      }).join('');
  }

  function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function debounce(fn, ms) {
    let timer;
    return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  }

  function destroy() {
    fewshotData = [];
    goldenData = [];
  }

  return { render, mount, destroy };
})();
