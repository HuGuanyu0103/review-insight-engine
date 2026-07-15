/**
 * Minimal reactive state store with event-based subscriptions.
 */
const Store = (() => {
  const state = {
    jobs: JSON.parse(localStorage.getItem('uv_jobs') || '{}'),
    activeJobId: localStorage.getItem('uv_active_job') || null,
  };

  const listeners = new Map();

  function get(key) {
    return state[key];
  }

  function set(key, value) {
    state[key] = value;
    if (key === 'jobs') {
      localStorage.setItem('uv_jobs', JSON.stringify(value));
    }
    if (key === 'activeJobId') {
      localStorage.setItem('uv_active', value || '');
    }
    (listeners.get(key) || []).forEach(fn => fn(value));
  }

  function on(key, fn) {
    if (!listeners.has(key)) listeners.set(key, []);
    listeners.get(key).push(fn);
    return () => {
      const arr = listeners.get(key) || [];
      listeners.set(key, arr.filter(f => f !== fn));
    };
  }

  function addJob(jobId, meta = {}) {
    const jobs = { ...state.jobs };
    jobs[jobId] = { id: jobId, status: 'pending', createdAt: new Date().toISOString(), ...meta };
    set('jobs', jobs);
    set('activeJobId', jobId);
  }

  function updateJob(jobId, update) {
    const jobs = { ...state.jobs };
    if (jobs[jobId]) {
      jobs[jobId] = { ...jobs[jobId], ...update };
      set('jobs', jobs);
    }
  }

  return { get, set, on, addJob, updateJob };
})();
