/**
 * Dashboard component — 三池指标仪表板（可点击展开评论内容）
 * Pools: all(全部) / filtered(已拦截) / hitl(待复核)
 */
const Dashboard = (() => {
  let currentJobId = null;
  let poolsData = null;

  async function render(jobId) {
    currentJobId = jobId;
    return `
      <div class="dashboard" id="dashboard">
        <div class="dash-loading">
          <div class="spinner"></div><span>加载数据池...</span>
        </div>
      </div>`;
  }

  async function mount(jobId, container) {
    currentJobId = jobId;
    await loadAndRender(container || document.getElementById('dashboard'));
  }

  async function loadAndRender(container) {
    if (!container || !currentJobId) return;

    try {
      const data = await API.getJobPools(currentJobId);
      poolsData = data.pools;
      container.innerHTML = buildHTML(poolsData);
      bindEvents(container);
    } catch (err) {
      container.innerHTML = `
        <div class="dash-error">
          <span>⚠️ 数据池加载失败: ${err.message}</span>
          <button class="btn btn-sm btn-outline" onclick="Dashboard.retry()">重试</button>
        </div>`;
    }
  }

  function buildHTML(pools) {
    const all = pools.all || { count: 0, reviews: [] };
    const filtered = pools.filtered || { count: 0, reviews: [] };
    const hitl = pools.hitl || { count: 0, reviews: [] };

    const passed = all.count - filtered.count;

    return `
      <div class="pool-metrics">
        <div class="pool-card pool-all" data-pool="all">
          <div class="pool-icon">📥</div>
          <div class="pool-info">
            <div class="pool-count">${all.count}</div>
            <div class="pool-label">全部评论</div>
          </div>
          <div class="pool-arrow">▶</div>
        </div>
        <div class="pool-connector">
          <div class="connector-line"></div>
          <div class="connector-split"></div>
        </div>
        <div class="pool-card pool-pass" data-pool="pass">
          <div class="pool-icon">✅</div>
          <div class="pool-info">
            <div class="pool-count">${passed}</div>
            <div class="pool-label">通过过滤</div>
          </div>
          <div class="pool-arrow">▶</div>
        </div>
        <div class="pool-card pool-filtered" data-pool="filtered">
          <div class="pool-icon">🛑</div>
          <div class="pool-info">
            <div class="pool-count">${filtered.count}</div>
            <div class="pool-label">已拦截</div>
          </div>
          <div class="pool-arrow">▶</div>
        </div>
        <div class="pool-connector">
          <div class="connector-line"></div>
        </div>
        <div class="pool-card pool-hitl" data-pool="hitl">
          <div class="pool-icon">🔍</div>
          <div class="pool-info">
            <div class="pool-count">${hitl.count}</div>
            <div class="pool-label">待人工复核</div>
          </div>
          <div class="pool-arrow">▶</div>
        </div>
        <div class="pool-card pool-final">
          <div class="pool-icon">📊</div>
          <div class="pool-info">
            <div class="pool-count">${all.count - filtered.count - hitl.count}</div>
            <div class="pool-label">入统计分析</div>
          </div>
        </div>
      </div>
      <div class="pool-detail" id="pool-detail" style="display:none;"></div>
    `;
  }

  function bindEvents(container) {
    container.querySelectorAll('.pool-card').forEach(card => {
      card.addEventListener('click', () => {
        const pool = card.dataset.pool;
        togglePoolDetail(pool, card);
      });
    });
  }

  function togglePoolDetail(pool, cardEl) {
    const detailEl = document.getElementById('pool-detail');
    if (!detailEl || !poolsData) return;

    // If same pool clicked, toggle off
    if (detailEl.style.display !== 'none' && detailEl.dataset.activePool === pool) {
      detailEl.style.display = 'none';
      document.querySelectorAll('.pool-card').forEach(c => c.classList.remove('active'));
      return;
    }

    // Highlight active card
    document.querySelectorAll('.pool-card').forEach(c => c.classList.remove('active'));
    if (cardEl) cardEl.classList.add('active');

    let reviews, label;
    if (pool === 'all') {
      reviews = poolsData.all.reviews;
      label = '全部评论';
    } else if (pool === 'filtered') {
      reviews = poolsData.filtered.reviews;
      label = '已拦截评论';
    } else if (pool === 'hitl') {
      reviews = poolsData.hitl.reviews;
      label = '待人工复核';
    } else if (pool === 'pass') {
      // "通过过滤" = all minus filtered
      const filteredIds = new Set((poolsData.filtered.reviews || []).map(r => r.review_id));
      reviews = (poolsData.all.reviews || []).filter(r => !filteredIds.has(r.review_id));
      label = '通过过滤的评论';
    } else {
      reviews = [];
      label = '';
    }

    const pageSize = 25;
    let page = 0;
    const totalPages = Math.ceil(reviews.length / pageSize);

    function renderPage() {
      const slice = reviews.slice(page * pageSize, (page + 1) * pageSize);
      detailEl.innerHTML = `
        <div class="pool-detail-header">
          <h4>${label} <span class="pool-detail-count">(${reviews.length} 条)</span></h4>
          <button class="btn btn-sm btn-outline pool-detail-close" onclick="document.getElementById('pool-detail').style.display='none'">✕ 关闭</button>
        </div>
        <div class="pool-detail-list">
          ${slice.map((r, i) => `
            <div class="pool-review-item">
              <div class="pri-index">${page * pageSize + i + 1}</div>
              <div class="pri-content">
                <div class="pri-text">${escapeHTML(r.content || r.review_content || '')}</div>
                <div class="pri-meta">
                  <code>${escapeHTML(r.review_id || '')}</code>
                  ${r.rating ? `<span>⭐${r.rating}</span>` : ''}
                  ${r.user_tier ? `<span class="tg tg-gray">${escapeHTML(r.user_tier)}</span>` : ''}
                  ${r.product_name ? `<span class="tg tg-blue">${escapeHTML(r.product_name)}</span>` : ''}
                  ${r.reason ? `<span class="tg tg-amber">${escapeHTML(r.reason)}</span>` : ''}
                  ${r.retry_count ? `<span class="text-muted">重试${r.retry_count}次</span>` : ''}
                </div>
              </div>
            </div>
          `).join('')}
        </div>
        ${totalPages > 1 ? `
          <div class="pool-detail-pager">
            <button class="btn btn-sm btn-outline" ${page === 0 ? 'disabled' : ''} id="pool-prev">上一页</button>
            <span>${page + 1} / ${totalPages}</span>
            <button class="btn btn-sm btn-outline" ${page >= totalPages - 1 ? 'disabled' : ''} id="pool-next">下一页</button>
          </div>` : ''}
      `;

      // Bind pager
      document.getElementById('pool-prev')?.addEventListener('click', () => { page--; renderPage(); });
      document.getElementById('pool-next')?.addEventListener('click', () => { page++; renderPage(); });
    }

    detailEl.dataset.activePool = pool;
    detailEl.style.display = 'block';
    renderPage();
    detailEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function escapeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
  }

  function retry() {
    const container = document.getElementById('dashboard');
    if (container) loadAndRender(container);
  }

  return { render, mount, retry };
})();
