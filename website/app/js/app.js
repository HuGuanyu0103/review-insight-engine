/**
 * Main Application — 商品评论洞察引擎 Frontend SPA
 */
(function () {
  'use strict';

  // ---- Route Registration ----

  // Home / Upload
  Router.register('/', async () => {
    const html = await UploadView.render();
    document.getElementById('app-content').innerHTML = html;
    UploadView.mount();
    highlightNav('/');
    return UploadView;
  });

  // Report view (with job ID)
  Router.register('/report/:jobId', async (params) => {
    const html = await ReportView.render(params);
    document.getElementById('app-content').innerHTML = html;
    await ReportView.mount(params);
    highlightNav('/report');
    return ReportView;
  });

  // Report without job ID — show helpful message instead of redirect
  Router.register('/report', async () => {
    const jobId = Store.get('activeJobId');
    if (jobId) {
      Router.navigate('/report/' + jobId);
      return null;
    }
    showEmptyState('report');
    highlightNav('/report');
    return null;
  });

  // RAG Q&A
  Router.register('/ask/:jobId', async (params) => {
    const html = await AskView.render(params);
    document.getElementById('app-content').innerHTML = html;
    AskView.mount(params);
    highlightNav('/ask');
    return AskView;
  });

  Router.register('/ask', async () => {
    const html = await AskView.render({});
    document.getElementById('app-content').innerHTML = html;
    AskView.mount({});
    highlightNav('/ask');
    return AskView;
  });

  // Samples Library (Few-shot + Golden)
  Router.register('/samples', async () => {
    const html = await SamplesView.render();
    document.getElementById('app-content').innerHTML = html;
    SamplesView.mount();
    highlightNav('/samples');
    return SamplesView;
  });

  // HITL Review
  Router.register('/hitl/:jobId', async (params) => {
    const html = await HITLView.render(params);
    document.getElementById('app-content').innerHTML = html;
    await HITLView.mount(params);
    highlightNav('/hitl');
    return HITLView;
  });

  Router.register('/hitl', async () => {
    const jobId = Store.get('activeJobId');
    if (jobId) {
      Router.navigate('/hitl/' + jobId);
      return null;
    }
    const html = await HITLView.render({});
    document.getElementById('app-content').innerHTML = html;
    HITLView.mount({});
    highlightNav('/hitl');
    return HITLView;
  });

  // ---- Empty State Helper ----

  function showEmptyState(page) {
    const titles = {
      report: '📊 报告',
      ask: '💬 问答',
      hitl: '🔍 复核',
    };
    const descs = {
      report: '洞察报告需要先完成评论数据分析。',
      ask: '语义问答基于已分析的评论数据。',
      hitl: '人工复核需要先完成分析，才有待审核项。',
    };

    document.getElementById('app-content').innerHTML = `
      <div class="view">
        <div class="view-header">
          <h1>${titles[page]}</h1>
          <p>${descs[page]}</p>
        </div>
        <div class="empty-state">
          <div class="empty-icon">📋</div>
          <h3>还没有分析任务</h3>
          <p>请先上传 CSV 评论数据进行分析，分析完成后即可在这里查看结果。</p>
          <button class="btn btn-primary mt-3" onclick="window.location.hash='#/'">
            📥 去上传数据
          </button>
        </div>
      </div>`;
  }

  // ---- Nav Highlight ----

  function highlightNav(path) {
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.remove('active');
      if (link.dataset.path === path || (path.startsWith('/report') && link.dataset.path === '/report')) {
        link.classList.add('active');
      }
    });
  }

  // ---- Nav Clicks ----

  document.addEventListener('click', (e) => {
    const link = e.target.closest('.nav-link');
    if (link) {
      e.preventDefault();
      Router.navigate(link.dataset.path);
    }
  });

  // ---- Backend Health Check ----

  let backendOnline = false;

  async function checkHealth() {
    const indicator = document.getElementById('health-indicator');
    const banner = document.getElementById('offline-banner');
    if (!indicator) return;
    try {
      await API.healthCheck();
      backendOnline = true;
      indicator.className = 'health-dot healthy';
      indicator.title = '后端服务正常';
      if (banner) banner.style.display = 'none';
    } catch (_) {
      backendOnline = false;
      indicator.className = 'health-dot unhealthy';
      indicator.title = '后端服务不可用 — 请启动后端';
      if (banner) banner.style.display = 'block';
    }
  }

  // ---- Init ----

  function init() {
    checkHealth();
    setInterval(checkHealth, 30000);
    Router.resolve();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
