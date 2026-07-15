/**
 * Upload View — CSV file upload + pipeline trigger
 */
const UploadView = (() => {
  async function render() {
    const jobs = Store.get('jobs');
    const recentJobs = Object.values(jobs).sort((a, b) =>
      new Date(b.createdAt) - new Date(a.createdAt)
    );

    return `
      <div class="view upload-view">
        <div class="view-header">
          <h1>📥 上传评论数据</h1>
          <p>上传 CSV 文件，自动触发全链路分析（解析 → 提取 → 统计 → 报告）</p>
        </div>

        <div class="upload-zone" id="upload-zone">
          <div class="upload-zone-inner">
            <div class="upload-icon">📁</div>
            <h3>拖拽 CSV 文件到此处</h3>
            <p>或点击下方按钮选择文件</p>
            <label class="btn btn-primary" id="select-file-btn" style="cursor:pointer;">
              📁 选择文件
              <input type="file" id="file-input" accept=".csv" style="display:none;">
            </label>
          </div>
          <div class="upload-progress hidden" id="upload-progress">
            <div class="spinner"></div>
            <p id="upload-progress-text">正在上传和分析...</p>
          </div>
          <div class="upload-success hidden" id="upload-success">
            <div class="success-icon">✅</div>
            <h3 id="upload-success-title">上传成功！</h3>
            <p id="upload-success-msg"></p>
            <div id="upload-quick-stats" style="display:none;"></div>
            <button class="btn btn-primary" id="view-report-btn">查看报告</button>
          </div>
          <div class="upload-error hidden" id="upload-error">
            <div class="error-icon">❌</div>
            <h3>上传失败</h3>
            <p id="upload-error-msg"></p>
            <button class="btn btn-outline" id="retry-upload-btn">重试</button>
          </div>
        </div>

        <div class="test-data-banner">
          <div class="test-data-icon">🧪</div>
          <div class="test-data-info">
            <strong>没有测试数据？</strong>下载预生成的 <strong>820 条</strong>电商评论测试集：
            <a href="data/test_reviews_820.csv" class="btn btn-primary btn-sm" download>📥 下载测试 CSV (820条)</a>
          </div>
        </div>

        <div class="csv-format-info">
          <h3>📋 CSV 文件格式要求</h3>
          <table class="format-table">
            <thead><tr><th>列名</th><th>必填</th><th>说明</th></tr></thead>
            <tbody>
              <tr><td><code>review_id</code></td><td><span class="badge badge-red">必填</span></td><td>评论唯一标识</td></tr>
              <tr><td><code>review_content</code></td><td><span class="badge badge-red">必填</span></td><td>评论正文</td></tr>
              <tr><td><code>review_date</code></td><td><span class="badge badge-red">必填</span></td><td>评论日期（YYYY-MM-DD）</td></tr>
              <tr><td><code>star_rating</code></td><td><span class="badge badge-green">可选</span></td><td>星级评分（1-5），用于交叉验证</td></tr>
              <tr><td><code>product_sku</code></td><td><span class="badge badge-green">可选</span></td><td>商品 SKU，用于 SKU 维度下钻</td></tr>
              <tr><td><code>user_level</code></td><td><span class="badge badge-green">可选</span></td><td>用户等级，用于用户分层分析</td></tr>
            </tbody>
          </table>
        </div>

        ${recentJobs.length > 0 ? `
          <div class="recent-jobs">
            <h3>📋 最近任务</h3>
            <div class="jobs-list">
              ${recentJobs.slice(0, 5).map(j => `
                <div class="job-item" data-job-id="${j.id}">
                  <div class="job-meta">
                    <span class="job-id">${j.id}</span>
                    <span class="job-date">${new Date(j.createdAt).toLocaleString('zh-CN')}</span>
                  </div>
                  <span class="job-status status-${j.status}">${statusLabel(j.status)}</span>
                  <button class="btn btn-sm btn-outline view-job-btn" data-job-id="${j.id}">查看</button>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}
      </div>
    `;
  }

  function statusLabel(s) {
    const map = {
      pending: '等待中', running: '分析中', completed: '已完成', failed: '失败',
    };
    return map[s] || s;
  }

  function mount() {
    const zone = document.getElementById('upload-zone');
    if (!zone) return;

    const fileInput = document.getElementById('file-input');
    const successEl = document.getElementById('upload-success');
    const errorEl = document.getElementById('upload-error');

    // File input change — called when user picks a file via label click or drag-drop
    if (fileInput) {
      fileInput.addEventListener('change', e => {
        const file = e.target.files[0];
        if (file) handleFile(file);
        fileInput.value = '';
      });
    }

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
      zone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); });
    });

    ['dragenter', 'dragover'].forEach(evt => {
      zone.addEventListener(evt, () => zone.classList.add('dragover'));
    });

    ['dragleave', 'drop'].forEach(evt => {
      zone.addEventListener(evt, () => zone.classList.remove('dragover'));
    });

    zone.addEventListener('drop', e => {
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });

    // Recent jobs click
    document.querySelectorAll('.view-job-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const jobId = btn.dataset.jobId;
        Store.set('activeJobId', jobId);
        Router.navigate('/report/' + jobId);
      });
    });

    // View report after upload
    const viewBtn = document.getElementById('view-report-btn');
    if (viewBtn) {
      viewBtn.addEventListener('click', () => {
        Router.navigate('/report/' + Store.get('activeJobId'));
      });
    }

    // Retry
    const retryBtn = document.getElementById('retry-upload-btn');
    if (retryBtn) {
      retryBtn.addEventListener('click', () => {
        errorEl.classList.add('hidden');
        zone.querySelector('.upload-zone-inner').style.display = '';
        fileInput.value = '';
      });
    }
  }

  async function handleFile(file) {
    if (!file.name.endsWith('.csv')) {
      showError('请选择 CSV 格式的文件');
      return;
    }

    const zone = document.getElementById('upload-zone');
    const inner = zone.querySelector('.upload-zone-inner');
    const progressEl = document.getElementById('upload-progress');
    const progressText = document.getElementById('upload-progress-text');
    const successEl = document.getElementById('upload-success');
    const errorEl = document.getElementById('upload-error');

    inner.style.display = 'none';
    errorEl.classList.add('hidden');
    successEl.classList.add('hidden');
    progressEl.classList.remove('hidden');
    progressText.textContent = '正在上传文件...';

    try {
      const result = await API.uploadCSV(file);
      const jobId = result.job_id;
      Store.addJob(jobId, { fileName: file.name, status: 'pending' });
      progressText.textContent = '文件已上传，任务已提交到后台...';

      // Quick poll (up to 60s), then let user navigate to report
      const completed = await pollJobUntilDone(jobId, progressText);

      progressEl.classList.add('hidden');
      if (completed) {
        successEl.classList.remove('hidden');
        document.getElementById('upload-success-msg').textContent =
          `任务 ${jobId} 已完成！文件 "${file.name}" 已分析完毕。`;
      } else {
        // Still running — show quick stats with link to full dashboard
        successEl.classList.remove('hidden');
        document.getElementById('upload-success-title').textContent = '任务已提交！';
        document.getElementById('upload-success-msg').innerHTML = `
          任务 <code>${jobId}</code> 正在后台分析中（820条约需2-3分钟）。<br>
          <a href="#/report/${jobId}" style="color:var(--accent);font-weight:600;">📊 查看实时进度与数据池 →</a>
        `;
        // Fetch pool counts for quick display
        API.getJobPools(jobId).then(data => {
          const pools = data.pools;
          if (pools) {
            const el = document.getElementById('upload-quick-stats');
            if (el) {
              el.innerHTML = `
                <div class="quick-stats">
                  <span>📥 全部: <strong>${pools.all?.count || 0}</strong></span>
                  <span>🛑 已拦截: <strong>${pools.filtered?.count || 0}</strong></span>
                  <span>🔍 待复核: <strong>${pools.hitl?.count || 0}</strong></span>
                </div>`;
              el.style.display = 'block';
            }
          }
        }).catch(() => {});
      }
    } catch (err) {
      progressEl.classList.add('hidden');
      showError(err.message);
    }
  }

  async function pollJobUntilDone(jobId, progressText, quickPollMs = 60000) {
    const start = Date.now();
    const statuses = ['正在提取特征...', '正在统计分析...', '正在生成报告...', '正在构建向量库...'];

    let i = 0;
    while (Date.now() - start < quickPollMs) {
      await sleep(2000);
      try {
        const status = await API.getJobStatus(jobId);
        Store.updateJob(jobId, { status: status.status });

        if (status.status === 'completed') return true;
        if (status.status === 'failed') throw new Error(status.error || '分析任务失败');

        if (status.status === 'running') {
          const elapsed = Math.floor((Date.now() - start) / 1000);
          progressText.textContent = `${statuses[i % statuses.length]} (已等待 ${elapsed}s)...`;
        } else {
          progressText.textContent = '等待任务启动...';
        }
        i++;
      } catch (err) {
        if (err.message.includes('not found')) {
          progressText.textContent = '等待任务启动...';
        } else {
          throw err;
        }
      }
    }
    return false; // still running, let user continue
  }

  function showError(msg) {
    const el = document.getElementById('upload-error');
    const msgEl = document.getElementById('upload-error-msg');
    if (el && msgEl) {
      el.classList.remove('hidden');
      msgEl.textContent = msg;
    }
  }

  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  function destroy() {}

  return { render, mount, destroy };
})();
