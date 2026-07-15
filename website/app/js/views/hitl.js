/**
 * HITL View — Human-In-The-Loop review queue management.
 */
const HITLView = (() => {
  let currentJobId = null;

  async function render(params) {
    currentJobId = params.jobId || Store.get('activeJobId') || '';
    return `
      <div class="view hitl-view">
        <div class="view-header">
          <h1>🔍 人工复核队列</h1>
          <p>HITL (Human-In-The-Loop) — 三级质量门控筛查出的待人工审核项</p>
        </div>

        <div class="hitl-info-cards">
          <div class="info-card">
            <div class="info-icon">1️⃣</div>
            <h4>置信度门控</h4>
            <p>confidence &lt; 0.7 → 直接入复核池</p>
          </div>
          <div class="info-card">
            <div class="info-icon">2️⃣</div>
            <h4>星级-情感交叉验证</h4>
            <p>5星 + 判负面 + conf &lt; 0.9 → 疑似反讽</p>
          </div>
          <div class="info-card">
            <div class="info-icon">3️⃣</div>
            <h4>反向矛盾检查</h4>
            <p>1星 + 判正面 → 评分录入异常</p>
          </div>
        </div>

        ${currentJobId ? `
          <div class="hitl-toolbar">
            <span>任务: <code>${currentJobId}</code></span>
            <button class="btn btn-outline btn-sm" id="btn-refresh-hitl">🔄 刷新</button>
          </div>
          <div id="hitl-content">
            <div class="loading-spinner"><div class="spinner"></div><p>加载复核队列...</p></div>
          </div>
        ` : `
          <div class="empty-state">
            <div class="empty-icon">📋</div>
            <h3>未关联任务</h3>
            <p>请先从报告页面跳转，或先上传 CSV 进行分析</p>
            <button class="btn btn-primary mt-3" onclick="window.location.hash='#/'">去上传</button>
          </div>
        `}
      </div>
    `;
  }

  async function mount(params) {
    currentJobId = params.jobId || Store.get('activeJobId') || '';
    if (!currentJobId) return;

    const refreshBtn = document.getElementById('btn-refresh-hitl');
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadHITLQueue());

    await loadHITLQueue();
  }

  async function loadHITLQueue() {
    const container = document.getElementById('hitl-content');
    if (!container) return;

    try {
      const result = await API.getHITLQueue(currentJobId);
      const items = result.items || [];

      if (items.length === 0) {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">✅</div>
            <h3>复核队列为空</h3>
            <p>所有评论均已通过三级质量门控，无需人工干预</p>
            <p class="text-muted">共 ${result.count || 0} 条</p>
          </div>`;
        return;
      }

      container.innerHTML = `
        <div class="hitl-summary">
          共 <strong>${result.count}</strong> 条待复核项
        </div>
        <div class="hitl-list">
          ${items.map((item, idx) => buildHITLItem(item, idx)).join('')}
        </div>`;
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <h3>加载失败</h3>
          <p>${err.message}</p>
        </div>`;
    }
  }

  function buildHITLItem(item, idx) {
    const reviewId = item.review_id || '';
    const content = item.review_content || item.core_issue_summary || '';
    const reason = item.failure_reason || item.gate_reason || '';
    const retryCount = item.retry_count || 0;

    return `
      <div class="hitl-card" id="hitl-${idx}">
        <div class="hitl-card-header">
          <div class="hitl-card-id">
            <span class="hitl-num">#${idx + 1}</span>
            <code>${reviewId}</code>
            ${reason ? `<span class="tg tg-amber">${reason}</span>` : ''}
          </div>
          <span class="text-muted">重试次数: ${retryCount}</span>
        </div>
        <div class="hitl-card-body">
          <div class="hitl-review-content">${escapeHTML(content)}</div>
        </div>
        <div class="hitl-card-actions">
          <div class="hitl-correction-form">
            <div class="form-group">
              <label>情感修正</label>
              <select class="hitl-sentiment" data-idx="${idx}">
                <option value="">保持原判</option>
                <option value="正面">正面</option>
                <option value="负面">负面</option>
                <option value="中性">中性</option>
                <option value="混合">混合</option>
              </select>
            </div>
            <div class="form-group">
              <label>分类修正</label>
              <select class="hitl-category" data-idx="${idx}">
                <option value="">保持原判</option>
                <option value="产品质量">产品质量</option>
                <option value="物流配送">物流配送</option>
                <option value="服务态度">服务态度</option>
                <option value="价格争议">价格争议</option>
                <option value="无效评论">无效评论</option>
              </select>
            </div>
            <div class="form-group">
              <label>紧急度</label>
              <select class="hitl-urgency" data-idx="${idx}">
                <option value="">保持原判</option>
                <option value="1">1 - 低优</option>
                <option value="2">2 - 中优</option>
                <option value="3">3 - 高优/红线</option>
              </select>
            </div>
            <button class="btn btn-primary btn-sm submit-hitl-btn" data-idx="${idx}" data-review-id="${reviewId}">
              提交修正
            </button>
          </div>
        </div>
      </div>`;
  }

  function mountHITLInteractions() {
    document.querySelectorAll('.submit-hitl-btn').forEach(btn => {
      btn.addEventListener('click', async function() {
        const idx = this.dataset.idx;
        const reviewId = this.dataset.reviewId;
        const card = document.getElementById('hitl-' + idx);

        const sentiment = card.querySelector('.hitl-sentiment').value;
        const category = card.querySelector('.hitl-category').value;
        const urgency = card.querySelector('.hitl-urgency').value;

        if (!sentiment && !category && !urgency) {
          alert('请至少选择一项修正');
          return;
        }

        const correction = {
          review_id: reviewId,
          sentiment: sentiment || '正面',
          primary_category: category || '产品质量',
          urgency_level: parseInt(urgency) || 1,
          core_issue_summary: '',
        };

        const originalText = this.textContent;
        this.textContent = '提交中...';
        this.disabled = true;

        try {
          await API.submitHITLCorrection(currentJobId, reviewId, correction);
          card.style.opacity = '0.5';
          card.style.borderColor = 'var(--green)';
          this.textContent = '✅ 已提交';
        } catch (err) {
          alert('提交失败: ' + err.message);
          this.textContent = originalText;
          this.disabled = false;
        }
      });
    });
  }

  // Re-mount interactions after rendering
  const origLoad = loadHITLQueue;
  loadHITLQueue = async function() {
    await origLoad();
    mountHITLInteractions();
  };

  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
  }

  function destroy() {
    currentJobId = null;
  }

  return { render, mount, destroy };
})();
