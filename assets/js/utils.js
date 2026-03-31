/**
 * IELTS Writing Mastery — Shared Utility Library
 * Version: 2.0 | Phase 1
 * 
 * Functions:
 *   showToast(message, type, duration)
 *   createTimer(options) → TimerController
 *   createWordCounter(textareaId, displayId, options)
 *   loadJSON(url) → Promise<data>
 *   storage.get/set/remove
 *   initResizer(handleId, leftColId)
 *   renderChart(canvasId, config) → Chart
 *   formatDate(ts)
 *   debounce(fn, delay)
 */

'use strict';

/* ==========================================================================
   TOAST NOTIFICATION
   ========================================================================== */

/**
 * @param {string} message
 * @param {'success'|'error'|'info'|'warning'} type
 * @param {number} duration ms
 */
function showToast(message, type = 'success', duration = 3500) {
  // Find or create container
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;display:flex;flex-direction:column;gap:.75rem;pointer-events:none;';
    document.body.appendChild(container);
  }

  const styles = {
    success: { bg: '#0f172a', border: '#10b981', icon: 'fa-check-circle', iconColor: '#10b981' },
    error: { bg: '#7f1d1d', border: '#ef4444', icon: 'fa-exclamation-circle', iconColor: '#fca5a5' },
    warning: { bg: '#451a03', border: '#f59e0b', icon: 'fa-exclamation-triangle', iconColor: '#fcd34d' },
    info: { bg: '#0c4a6e', border: '#0ea5e9', icon: 'fa-info-circle', iconColor: '#7dd3fc' },
  };
  const s = styles[type] || styles.success;

  const toast = document.createElement('div');
  toast.style.cssText = `
    display:flex;align-items:center;gap:.75rem;
    background:${s.bg};border-left:3px solid ${s.border};
    color:#f8fafc;padding:.875rem 1.25rem;border-radius:.75rem;
    box-shadow:0 10px 40px rgba(0,0,0,.3);
    min-width:260px;max-width:380px;pointer-events:all;
    animation:slideUp .3s ease forwards;
    font-family:'Inter',sans-serif;font-size:.875rem;
  `;
  toast.innerHTML = `
    <i class="fas ${s.icon}" style="color:${s.iconColor};font-size:1rem;flex-shrink:0;"></i>
    <span style="flex:1;line-height:1.4;">${message}</span>
    <button onclick="this.parentElement.remove()" style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:.75rem;padding:0;margin-left:.5rem;">✕</button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideDown .3s ease forwards';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

/* ==========================================================================
   COUNTDOWN TIMER
   ========================================================================== */

/**
 * Creates a controllable timer.
 * @param {object} opts
 *   displayId   — element id to update
 *   minutes     — initial minutes (default 40)
 *   onTick      — callback(secondsLeft)
 *   onComplete  — callback when reaches 0
 * @returns {{ start, pause, reset, toggle, isRunning }}
 */
function createTimer({ displayId, minutes = 40, onTick = null, onComplete = null } = {}) {
  const display = document.getElementById(displayId);
  let totalSeconds = minutes * 60;
  let remaining = totalSeconds;
  let interval = null;
  let running = false;

  function formatTime(secs) {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  }

  function update() {
    if (display) display.textContent = formatTime(remaining);
    if (onTick) onTick(remaining);
  }

  function start() {
    if (running) return;
    running = true;
    interval = setInterval(() => {
      if (remaining <= 0) {
        clearInterval(interval);
        running = false;
        if (onComplete) onComplete();
        return;
      }
      remaining--;
      update();
    }, 1000);
  }

  function pause() {
    clearInterval(interval);
    running = false;
  }

  function reset(newMinutes) {
    pause();
    remaining = (newMinutes || minutes) * 60;
    totalSeconds = remaining;
    update();
  }

  function toggle() {
    running ? pause() : start();
    return running;
  }

  function getTimeSpent() {
    return totalSeconds - remaining;
  }

  // Initial render
  update();

  return { start, pause, reset, toggle, isRunning: () => running, getTimeSpent };
}

/* ==========================================================================
   WORD COUNTER
   ========================================================================== */

/**
 * Attaches a live word counter to a textarea.
 * @param {string} textareaId
 * @param {string} displayId
 * @param {object} opts
 *   target     — minimum target word count (default 250)
 *   onUpdate   — callback(wordCount)
 */
function createWordCounter(textareaId, displayId, { target = 250, onUpdate = null } = {}) {
  const textarea = document.getElementById(textareaId);
  const display = document.getElementById(displayId);
  if (!textarea || !display) return;

  function count() {
    const words = textarea.value.trim().split(/\s+/).filter(w => w.length > 0).length;
    display.textContent = words;

    // Color coding
    display.className = display.className.replace(/\bwc-\w+/g, '');
    if (words === 0) { /* no class */ }
    else if (words < target * .6) { display.classList.add('wc-low'); }
    else if (words < target) { display.classList.add('wc-medium'); }
    else if (words < target * 1.3) { display.classList.add('wc-adequate'); }
    else { display.classList.add('wc-excellent'); }

    if (onUpdate) onUpdate(words);
    return words;
  }

  textarea.addEventListener('input', count);
  return { count, getCount: count };
}

/* ==========================================================================
   FETCH / JSON LOADER
   ========================================================================== */

/**
 * Loads a JSON file with error handling.
 * @param {string} url
 * @returns {Promise<any>}
 */
async function loadJSON(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`);
    return await res.json();
  } catch (err) {
    console.error('[loadJSON] Failed to load:', url, err);
    return null;
  }
}

/* ==========================================================================
   LOCAL STORAGE HELPERS
   ========================================================================== */

const storage = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (err) { console.warn('[storage.set]', err); }
  },
  remove(key) { localStorage.removeItem(key); },
  update(key, updater, fallback = null) {
    const current = this.get(key, fallback);
    this.set(key, updater(current));
  }
};

/* ==========================================================================
   DARK MODE TOGGLE
   ========================================================================== */

function toggleDarkMode() {
  const html = document.documentElement;
  const isDark = html.classList.toggle('dark');
  storage.set('darkMode', isDark ? 'enabled' : 'disabled');
  
  // Update icons globally
  updateDarkModeIcons(isDark);
}

function updateDarkModeIcons(isDark) {
  const moonIcons = document.querySelectorAll('.dark-icon-moon, [data-lucide="moon"]');
  const sunIcons = document.querySelectorAll('.dark-icon-sun, [data-lucide="sun"]');
  
  moonIcons.forEach(el => {
    if (isDark) el.classList.add('hidden'); else el.classList.remove('hidden');
    if (el.getAttribute('data-lucide')) el.setAttribute('data-lucide', isDark ? 'sun' : 'moon');
  });

  // Re-run Lucide if needed
  if (window.lucide) lucide.createIcons();
}

function initDarkMode() {
  const pref = storage.get('darkMode');
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const isDark = pref === 'enabled' || (!pref && systemDark);
  
  if (isDark) {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

/* ==========================================================================
   COLUMN RESIZER
   ========================================================================== */

/**
 * Initializes a drag-to-resize handle between two columns.
 * @param {string} handleId
 * @param {string} leftColId
 * @param {object} opts  { minWidth, maxWidth }
 */
function initResizer(handleId, leftColId, { minWidth = 280, maxWidth = 900 } = {}) {
  const handle = document.getElementById(handleId);
  const leftCol = document.getElementById(leftColId);
  if (!handle || !leftCol) return;

  let startX, startW;

  handle.addEventListener('mousedown', e => {
    e.preventDefault();
    startX = e.clientX;
    startW = leftCol.getBoundingClientRect().width;
    handle.classList.add('dragging');
    document.onselectstart = () => false;

    const onMove = e => {
      const w = Math.min(Math.max(startW + e.clientX - startX, minWidth), maxWidth);
      leftCol.style.width = w + 'px';
    };
    const onUp = () => {
      handle.classList.remove('dragging');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.onselectstart = null;
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

/* ==========================================================================
   CHART RENDERER
   ========================================================================== */

/**
 * Renders or updates a Chart.js chart.
 * @param {string} canvasId
 * @param {object} config — Chart.js config object
 * @returns {Chart|null}
 */
function renderChart(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return null;

  // Destroy existing chart if any
  let existing = Chart.getChart(canvas);
  if (existing) existing.destroy();

  return new Chart(canvas, config);
}

/* ==========================================================================
   ACCORDION TOGGLE
   ========================================================================== */

function toggleAccordion(id) {
  const wrapper = document.getElementById(id);
  const content = document.getElementById(`${id}-content`);
  const icon = document.getElementById(`${id}-icon`);
  if (!content) return;

  const isOpen = content.classList.toggle('expanded');
  if (icon) icon.style.transform = isOpen ? 'rotate(180deg)' : '';
}

/* ==========================================================================
   MISC HELPERS
   ========================================================================== */

function debounce(fn, delay = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleDateString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit'
  });
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function getWordCount(text) {
  return (text || '').trim().split(/\s+/).filter(w => w.length > 0).length;
}

/* ==========================================================================
   PROGRESS STATS (Hub Dashboard)
   ========================================================================== */

function getOverallProgress() {
  const history = storage.get('ieltsHistory', []);
  const streak = storage.get('ieltsStreakData', { current: 0, longest: 0 });
  const total = history.length;
  const words = history.reduce((acc, h) => acc + (h.wordCount || 0), 0);
  return { total, words, streak: streak.current, longestStreak: streak.longest };
}

// Auto-initialize dark mode on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initDarkMode);
} else {
  initDarkMode();
}
