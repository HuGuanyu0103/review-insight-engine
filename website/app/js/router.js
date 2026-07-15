/**
 * Simple hash-based SPA router.
 */
const Router = (() => {
  const routes = {};
  let currentView = null;
  let onRouteChange = null;

  function register(path, handler) {
    routes[path] = handler;
  }

  function navigate(path) {
    window.location.hash = path;
  }

  function getCurrentPath() {
    return window.location.hash.slice(1) || '/';
  }

  async function resolve() {
    const path = getCurrentPath();
    const app = document.getElementById('app-content');
    if (!app) return;

    // Cleanup previous view
    if (currentView && currentView.destroy) {
      currentView.destroy();
    }

    app.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>加载中...</p></div>';

    // Find matching route (supports /report/:id pattern)
    let handler = routes[path];
    let params = {};

    if (!handler) {
      for (const [pattern, h] of Object.entries(routes)) {
        const regex = new RegExp('^' + pattern.replace(/:\w+/g, '([^/]+)') + '$');
        const match = path.match(regex);
        if (match) {
          handler = h;
          const keys = [...pattern.matchAll(/:(\w+)/g)].map(m => m[1]);
          keys.forEach((k, i) => { params[k] = match[i + 1]; });
          break;
        }
      }
    }

    if (!handler) {
      app.innerHTML = `<div class="empty-state"><div class="empty-icon">🔍</div><h3>页面未找到</h3><p>路径 "${path}" 不存在</p></div>`;
      return;
    }

    try {
      currentView = await handler(params);
    } catch (err) {
      console.error('Route error:', err);
      app.innerHTML = `<div class="empty-state"><div class="empty-icon">⚠️</div><h3>加载失败</h3><p>${err.message}</p></div>`;
    }

    if (onRouteChange) onRouteChange(path);
  }

  function onChange(fn) {
    onRouteChange = fn;
  }

  window.addEventListener('hashchange', resolve);
  window.addEventListener('DOMContentLoaded', resolve);

  return { register, navigate, getCurrentPath, resolve, onChange };
})();
