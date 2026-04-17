/**
 * main.js  —  App orchestration
 * Wires the editor, pipeline, API call, player and step table together.
 */
'use strict';

const API_BASE = '';   // same origin — Flask serves both

// ── DOM refs ──────────────────────────────────────────────────────────────────
const langSelect    = document.getElementById('lang-select');
const traceBtn      = document.getElementById('trace-btn');
const clearBtn      = document.getElementById('clear-btn');
const sampleBtn     = document.getElementById('sample-btn');
const themeToggle   = document.getElementById('theme-toggle');

const emptyState    = document.getElementById('empty-state');
const loadingState  = document.getElementById('loading-state');
const errorState    = document.getElementById('error-state');
const resultState   = document.getElementById('result-state');

const loadingMsg    = document.getElementById('loading-msg');
const errorTitle    = document.getElementById('error-title');
const errorBody     = document.getElementById('error-body');
const errorLine     = document.getElementById('error-line');

const traceVideo    = document.getElementById('trace-video');
const videoBadge    = document.getElementById('video-step-badge');
const downloadLink  = document.getElementById('download-link');

const statSteps     = document.getElementById('stat-steps');
const statLang      = document.getElementById('stat-lang');
const statLines     = document.getElementById('stat-lines');
const statErrCard   = document.getElementById('stat-error-card');

const stepsToggle   = document.getElementById('steps-toggle');
const stepsWrapper  = document.getElementById('steps-table-wrapper');
const stepsChevron  = document.getElementById('steps-chevron');
const stepsCount    = document.getElementById('steps-count');
const stepsTbody    = document.getElementById('steps-tbody');

// Pipeline steps
const pipeSteps = {
  syntax: document.getElementById('pipe-syntax'),
  trace:  document.getElementById('pipe-trace'),
  frames: document.getElementById('pipe-frames'),
  video:  document.getElementById('pipe-video'),
};

// ── Theme management ──────────────────────────────────────────────────────────
(function applyStoredTheme() {
  const stored = localStorage.getItem('trace-theme');
  if (stored === 'light') {
    document.documentElement.classList.add('light-mode');
  }
})();

function toggleTheme() {
  const root   = document.documentElement;
  const isNowLight = root.classList.toggle('light-mode');
  localStorage.setItem('trace-theme', isNowLight ? 'light' : 'dark');
  // Update CodeMirror theme (dark=true when NOT light-mode)
  if (window.TraceEditor && TraceEditor.setEditorTheme) {
    TraceEditor.setEditorTheme(!isNowLight);
  }
  themeToggle.setAttribute('aria-label',
    isNowLight ? 'Switch to dark mode' : 'Switch to light mode');
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  TraceEditor.initEditor();
  bindEvents();
  // Sync toggle aria-label to current state
  const isLight = document.documentElement.classList.contains('light-mode');
  themeToggle.setAttribute('aria-label',
    isLight ? 'Switch to dark mode' : 'Switch to light mode');
});

// ── Events ────────────────────────────────────────────────────────────────────
function bindEvents() {
  traceBtn.addEventListener('click', runTrace);
  clearBtn.addEventListener('click', () => TraceEditor.clearEditor());
  sampleBtn.addEventListener('click', () => {
    const lang = langSelect.value;
    TraceEditor.loadSample(lang);
  });

  langSelect.addEventListener('change', () => {
    TraceEditor.switchLanguage(langSelect.value);
    resetPipeline();
    showPanel('empty');
  });

  stepsToggle.addEventListener('click', toggleSteps);

  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }
}

// ── Main trace flow ───────────────────────────────────────────────────────────
async function runTrace() {
  const code = TraceEditor.getCode().trim();
  if (!code) {
    showError('No code', 'Please write or paste some code before running the trace.', null);
    return;
  }

  const language = langSelect.value;

  traceBtn.disabled = true;
  traceBtn.innerHTML = '<span class="btn-icon">⏳</span> Tracing…';
  resetPipeline();
  showPanel('loading');

  try {
    // ── Step 1: Syntax ───────────────────────────────────────────────────────
    setPipeStep('syntax', 'active');
    setLoadingMsg('Checking syntax…');
    await tick();

    const response = await fetch(`${API_BASE}/api/trace`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ code, language }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || `Server error ${response.status}`);
    }

    // Syntax error
    if (data.syntax_error) {
      setPipeStep('syntax', 'error');
      showError(
        'Syntax Error',
        data.error,
        data.error_line ? `on line ${data.error_line}` : null
      );
      return;
    }

    setPipeStep('syntax', 'done');

    // ── Step 2–4: Trace, frames, video (all happen server-side) ─────────────
    setPipeStep('trace',  'active');
    setLoadingMsg('Tracing execution…');
    await tick(300);
    setPipeStep('trace',  'done');

    setPipeStep('frames', 'active');
    setLoadingMsg('Rendering frames…');
    await tick(200);
    setPipeStep('frames', 'done');

    setPipeStep('video', 'active');
    setLoadingMsg('Building video…');
    await tick(200);
    setPipeStep('video', 'done');

    // ── Show results ─────────────────────────────────────────────────────────
    renderResults(data);

  } catch (err) {
    showError('Request Failed', err.message, null);
    Object.values(pipeSteps).forEach(el => el.classList.remove('active', 'done'));
  } finally {
    traceBtn.disabled = false;
    traceBtn.innerHTML = '<span class="btn-icon">▶</span> Run Trace';
  }
}

// ── Render results ────────────────────────────────────────────────────────────
function renderResults(data) {
  const { video_url, steps, total_steps, has_runtime_error, language } = data;
  const code = TraceEditor.getCode();

  // Stats
  statSteps.textContent = total_steps;
  statLang.textContent  = language.charAt(0).toUpperCase() + language.slice(1);
  statLines.textContent = code.split('\n').length;
  statErrCard.style.display = has_runtime_error ? '' : 'none';

  // Steps table
  stepsCount.textContent = total_steps;
  buildStepsTable(steps);

  // Video
  const fullUrl = `${API_BASE}${video_url}`;
  downloadLink.href = fullUrl;
  TracePlayer.init(traceVideo, videoBadge, stepsTbody, steps, 2);
  TracePlayer.loadVideo(fullUrl);

  showPanel('result');
}

// ── Step table ────────────────────────────────────────────────────────────────
function buildStepsTable(steps) {
  stepsTbody.innerHTML = '';

  steps.forEach((step, i) => {
    const tr = document.createElement('tr');
    tr.dataset.step = i + 1;

    const isError = step.event === 'error' || step.event === 'exception';
    if (isError) tr.classList.add('row-error');

    const localsStr = step.locals && Object.keys(step.locals).length
      ? Object.entries(step.locals)
          .slice(0, 4)
          .map(([k, v]) => `${k}=${v}`)
          .join('  ')
      : '—';

    const outPrev = (step.stdout || '').trim();
    const outDisp = outPrev ? outPrev.split('\n').pop().slice(0, 40) : '—';
    const errDisp = step.error ? step.error.slice(0, 50) : null;

    tr.innerHTML = `
      <td>${i + 1}</td>
      <td>${step.line ?? '?'}</td>
      <td>${eventBadge(step.event)}</td>
      <td class="step-locals" title="${escHtml(localsStr)}">${escHtml(localsStr)}</td>
      <td>${errDisp ? `<span style="color:var(--red)">${escHtml(errDisp)}</span>` : escHtml(outDisp)}</td>
    `;

    stepsTbody.appendChild(tr);
  });
}

function eventBadge(event) {
  const map = {
    line:      '<span style="color:var(--green)">line</span>',
    call:      '<span style="color:var(--blue)">call</span>',
    return:    '<span style="color:var(--cyan)">return</span>',
    exception: '<span style="color:var(--orange)">exception</span>',
    error:     '<span style="color:var(--red)">error</span>',
    output:    '<span style="color:var(--purple)">output</span>',
  };
  return map[event] || `<span>${escHtml(event)}</span>`;
}

// ── Steps toggle ──────────────────────────────────────────────────────────────
function toggleSteps() {
  const expanded = stepsToggle.getAttribute('aria-expanded') === 'true';
  stepsToggle.setAttribute('aria-expanded', !expanded);
  stepsWrapper.classList.toggle('hidden', expanded);
}

// ── Pipeline helpers ──────────────────────────────────────────────────────────
function setPipeStep(name, state) {
  const el = pipeSteps[name];
  if (!el) return;
  el.classList.remove('active', 'done', 'error');
  el.classList.add(state);
}

function resetPipeline() {
  Object.values(pipeSteps).forEach(el =>
    el.classList.remove('active', 'done', 'error')
  );
}

// ── Panel visibility ──────────────────────────────────────────────────────────
function showPanel(which) {
  emptyState  .classList.toggle('hidden', which !== 'empty');
  loadingState.classList.toggle('hidden', which !== 'loading');
  errorState  .classList.toggle('hidden', which !== 'error');
  resultState .classList.toggle('hidden', which !== 'result');
}

function showError(title, body, line) {
  errorTitle.textContent = title || 'Error';
  errorBody.textContent  = body  || '';
  errorLine.textContent  = line  || '';
  showPanel('error');
}

function setLoadingMsg(msg) {
  if (loadingMsg) loadingMsg.textContent = msg;
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function tick(ms = 50) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
