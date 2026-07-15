/**
 * Ask View — RAG-powered natural language Q&A interface.
 */
const AskView = (() => {
  let conversation = [];

  async function render(params) {
    const jobId = params.jobId || Store.get('activeJobId') || '';
    return `
      <div class="view ask-view">
        <div class="view-header">
          <h1>💬 语义问答</h1>
          <p>基于评论数据的自然语言查询——AI 仅基于实际评论回答，绝不编造</p>
        </div>

        <div class="ask-layout">
          <div class="ask-sidebar">
            <h4>💡 建议问法</h4>
            <div class="suggested-questions">
              <button class="sq-btn" data-q="鞋子掉色问题主要集中在什么颜色？">鞋子掉色问题主要集中在什么颜色？</button>
              <button class="sq-btn" data-q="用户最不满意的是哪些方面？">用户最不满意的是哪些方面？</button>
              <button class="sq-btn" data-q="Plus会员对质量有什么反馈？">Plus会员对质量有什么反馈？</button>
              <button class="sq-btn" data-q="最近一周物流投诉有没有增加？">最近一周物流投诉有没有增加？</button>
              <button class="sq-btn" data-q="哪些SKU的差评率最高？">哪些SKU的差评率最高？</button>
              <button class="sq-btn" data-q="用户提到最多的质量问题是什么？">用户提到最多的质量问题是什么？</button>
            </div>
            ${jobId ? `<div class="ask-job-info mt-3"><span class="text-muted">关联任务:</span> <code>${jobId}</code></div>` : ''}
          </div>
          <div class="ask-main">
            <div class="chat-container" id="chat-container">
              <div class="chat-welcome">
                <div class="welcome-icon">🤖</div>
                <h3>评论洞察引擎 · 智能问答</h3>
                <p>基于 RAG 技术，您可以用自然语言提问，系统会从评论数据中检索相关内容并生成带引用来源的回答。</p>
                <p class="text-muted">点击左侧建议问法，或直接输入问题开始</p>
              </div>
            </div>

            <div class="chat-input-area">
              <div class="chat-input-row">
                <input type="text" id="question-input"
                  placeholder="输入你的问题，例如：鞋子掉色问题主要集中在什么颜色？"
                  autocomplete="off">
                <button class="btn btn-primary" id="ask-btn">
                  <span id="ask-btn-text">发送</span>
                  <span class="spinner-small hidden" id="ask-spinner"></span>
                </button>
              </div>
              <div class="chat-input-options">
                <label class="option-label">
                  检索数量:
                  <select id="n-results-select">
                    <option value="5">5 条</option>
                    <option value="10" selected>10 条</option>
                    <option value="20">20 条</option>
                  </select>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function mount() {
    const input = document.getElementById('question-input');
    const askBtn = document.getElementById('ask-btn');
    const chatContainer = document.getElementById('chat-container');

    if (!input || !askBtn) return;

    // Suggested questions
    document.querySelectorAll('.sq-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        input.value = btn.dataset.q;
        submitQuestion();
      });
    });

    askBtn.addEventListener('click', submitQuestion);
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') submitQuestion();
    });
  }

  async function submitQuestion() {
    const input = document.getElementById('question-input');
    const askBtn = document.getElementById('ask-btn');
    const askBtnText = document.getElementById('ask-btn-text');
    const spinner = document.getElementById('ask-spinner');
    const chatContainer = document.getElementById('chat-container');

    const question = input.value.trim();
    if (!question) return;

    const nResults = parseInt(document.getElementById('n-results-select').value);

    // Hide welcome
    const welcome = chatContainer.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    conversation.push({ role: 'user', content: question });
    renderConversation(chatContainer);

    // Loading state
    input.value = '';
    input.disabled = true;
    askBtn.disabled = true;
    askBtnText.textContent = '搜索中...';
    spinner.classList.remove('hidden');

    // Add loading bubble
    const loadingId = 'loading-' + Date.now();
    chatContainer.insertAdjacentHTML('beforeend', `
      <div class="chat-message assistant" id="${loadingId}">
        <div class="msg-avatar">🤖</div>
        <div class="msg-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>
      </div>`);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    try {
      const result = await API.askQuestion(question, nResults);
      conversation.push({
        role: 'assistant',
        content: result.answer,
        citations: result.citations || [],
        retrievedCount: result.retrieved_count,
      });

      // Remove loading
      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();
    } catch (err) {
      const loadingEl = document.getElementById(loadingId);
      if (loadingEl) loadingEl.remove();
      conversation.push({
        role: 'assistant',
        content: `❌ 查询失败：${err.message}`,
        citations: [],
      });
    }

    renderConversation(chatContainer);
    input.disabled = false;
    askBtn.disabled = false;
    askBtnText.textContent = '发送';
    spinner.classList.add('hidden');
    input.focus();
  }

  function renderConversation(container) {
    // Remove existing rendered messages (keep only the input area if it's inside)
    container.querySelectorAll('.chat-message').forEach(el => el.remove());

    conversation.forEach((msg, i) => {
      const isUser = msg.role === 'user';
      const citationsHTML = msg.citations && msg.citations.length > 0 ? `
        <div class="msg-citations">
          <div class="citations-title">📎 引用评论 (${msg.retrievedCount || msg.citations.length} 条)</div>
          ${msg.citations.map(c => `
            <div class="citation-item">
              <span class="citation-index">[${c.index}]</span>
              <span class="citation-meta">${c.review_id || ''} | ${c.sentiment || ''} | ${c.category || ''}</span>
              <span class="citation-content">${(c.content || '').slice(0, 150)}...</span>
            </div>
          `).join('')}
        </div>` : '';

      container.insertAdjacentHTML('beforeend', `
        <div class="chat-message ${isUser ? 'user' : 'assistant'}">
          <div class="msg-avatar">${isUser ? '👤' : '🤖'}</div>
          <div class="msg-bubble">
            <div class="msg-text">${escapeHTML(msg.content)}</div>
            ${citationsHTML}
          </div>
        </div>
      `);
    });

    container.scrollTop = container.scrollHeight;
  }

  function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML.replace(/\n/g, '<br>');
  }

  function destroy() {
    conversation = [];
  }

  return { render, mount, destroy };
})();
