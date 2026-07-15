/**
 * API Client for 商品评论洞察引擎
 * Communicates with the FastAPI backend endpoints.
 */
const API = (() => {
  const BASE = '';

  async function request(url, options = {}) {
    const config = {
      headers: { 'Accept': 'application/json' },
      ...options,
    };
    // Don't set Content-Type for FormData (browser sets it with boundary)
    if (!(options.body instanceof FormData)) {
      config.headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(BASE + url, config);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  }

  return {
    /** Upload CSV and trigger analysis pipeline */
    uploadCSV(file) {
      const form = new FormData();
      form.append('file', file);
      return request('/api/upload', { method: 'POST', body: form });
    },

    /** Poll job status */
    getJobStatus(jobId) {
      return request(`/api/status/${jobId}`);
    },

    /** Get insight report */
    getReport(jobId) {
      return request(`/api/report/${jobId}`);
    },

    /** RAG Q&A */
    askQuestion(question, nResults = 10) {
      return request('/api/ask', {
        method: 'POST',
        body: JSON.stringify({ question, n_results: nResults }),
      });
    },

    /** Get HITL queue */
    getHITLQueue(jobId) {
      return request(`/api/hitl/${jobId}`);
    },

    /** Submit HITL correction */
    submitHITLCorrection(jobId, reviewId, correction) {
      return request(`/api/hitl/${jobId}/${reviewId}`, {
        method: 'POST',
        body: JSON.stringify(correction),
      });
    },

    /** Get three review pools (all/filtered/hitl) with content */
    getJobPools(jobId) {
      return request(`/api/job/${jobId}/pools`);
    },

    /** Health check */
    healthCheck() {
      return request('/health');
    },
  };
})();
