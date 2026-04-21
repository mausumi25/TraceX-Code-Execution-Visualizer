'use strict';
/**
 * visualizer.js — Interactive Algorithm Visualizer
 * Renders execution steps as live DOM animations:
 *   - Array boxes with colour states (compare / swap / sorted / found)
 *   - Face-to-face comparison zone
 *   - Variable panel with change flashing
 *   - Call stack display
 *   - Beginner-friendly explanations
 *   - Play / Pause / Prev / Next / Speed controls
 */

// ── Known pointer-variable colours ───────────────────────────────────────────
const PTR_COLORS = {
  i:'#ffd428', j:'#ff8c1a', k:'#c87fff', l:'#3c96ff', r:'#f85149',
  low:'#3c96ff', high:'#f85149', mid:'#bc8cff',
  left:'#3c96ff', right:'#f85149', start:'#3c96ff', end:'#f85149',
  pivot:'#c43bdc', slow:'#3fb950', fast:'#4fc5e8',
  p:'#ffd428', q:'#ff8c1a', curr:'#3fb950', prev:'#3c96ff',
  ans:'#3fb950', idx:'#ffd428', pos:'#ffd428',
  min_idx:'#3fb950', max_idx:'#f85149',
};

// Variables that accumulate a "best" result
const RESULT_VARS = new Set([
  'max','min','result','ans','maximum','minimum','largest','smallest',
  'max_val','min_val','res','found','flag','count','total','sum','product',
  'output','target','key','val','value',
]);

// ── Utility helpers ───────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function tryParseNumList(s) {
  if (typeof s !== 'string') return null;
  s = s.replace(/[…]{1,}|\.\.\./g, '').trim();
  if (!s.startsWith('[') || !s.endsWith(']')) return null;
  try {
    const a = JSON.parse(s.replace(/'/g, '"'));
    if (Array.isArray(a) && a.length >= 2 && a.every(x => typeof x === 'number'))
      return a;
  } catch {}
  return null;
}

function fmtVal(v) {
  if (typeof v === 'number' && Number.isInteger(v)) return String(v);
  if (typeof v === 'number') return v.toFixed(2);
  return String(v);
}

// ── TraceVisualizer class ─────────────────────────────────────────────────────
class TraceVisualizer {
  /**
   * @param {object} opts
   *   steps        — array of step objects from /api/trace
   *   codeLines    — string[] of source code lines
   *   language     — 'python' | 'javascript' | 'c' | 'cpp'
   *   algoName     — detected algorithm name
   *   els          — { codeEl, arrayEl, explainEl, varsEl, stackEl,
   *                    stepCountEl, progressEl, codeBadgeEl, outputEl, outputAreaEl }
   */
  constructor(opts) {
    this.steps    = opts.steps;
    this.lines    = opts.codeLines;
    this.lang     = (opts.language || '').toUpperCase();
    this.algo     = opts.algoName || 'Algorithm Execution';
    this.els      = opts.els;

    this.cur      = 0;
    this.playing  = false;
    this.speed    = 1;
    this._timer   = null;
    this._prevLoc = {};

    this._buildCode();
    this.goTo(0);
  }

  // ── Build code panel (once) ─────────────────────────────────────────────────
  _buildCode() {
    const el = this.els.codeEl;
    if (!el) return;
    el.innerHTML = '';
    this.lines.forEach((line, i) => {
      const row = document.createElement('div');
      row.className = 'code-line';
      row.dataset.ln = i + 1;
      row.innerHTML =
        `<span class="code-gutter">${i + 1}</span>` +
        `<span class="code-text">${esc(line)}</span>`;
      el.appendChild(row);
    });
  }

  _highlightLine(ln, isErr) {
    const el = this.els.codeEl;
    if (!el) return;
    el.querySelectorAll('.code-line').forEach(r =>
      r.classList.remove('active', 'error-line'));
    const row = el.querySelector(`[data-ln="${ln}"]`);
    if (row) {
      row.classList.add(isErr ? 'error-line' : 'active');
      row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
    if (this.els.codeBadgeEl)
      this.els.codeBadgeEl.textContent = `Line ${ln}`;
  }

  // ── Main render ─────────────────────────────────────────────────────────────
  goTo(idx) {
    if (idx < 0 || idx >= this.steps.length) return;
    this.cur = idx;
    const step     = this.steps[idx];
    const prevStep = idx > 0 ? this.steps[idx - 1] : null;
    const locs     = step.locals || {};
    const isErr    = step.event === 'error' || step.event === 'exception';

    this._highlightLine(step.line, isErr || !!step.error);
    this._renderArray(step, prevStep, locs);
    this._renderVars(locs, prevStep ? prevStep.locals || {} : {});
    this._renderExplain(step, prevStep);
    this._renderStack(step.stack || []);
    this._renderOutput(step.stdout || '');
    this._updateMeta();
    this._prevLoc = locs;
  }

  // ── Array visualization ─────────────────────────────────────────────────────
  _renderArray(step, prevStep, locs) {
    const el = this.els.arrayEl;
    if (!el) return;

    // Find main array
    let arrName = null, arr = null;
    for (const [k, v] of Object.entries(locs)) {
      const p = tryParseNumList(String(v));
      if (p && (!arr || p.length > arr.length)) { arrName = k; arr = p; }
    }

    if (!arr) {
      el.innerHTML = '<p class="no-arr">No array data detected at this step</p>';
      return;
    }

    const n = arr.length;

    // Previous array snapshot (for swap detection)
    let prevArr = null;
    if (prevStep) {
      const pv = (prevStep.locals || {})[arrName];
      if (pv) prevArr = tryParseNumList(String(pv));
    }

    // Pointer positions
    const ptrs = {};
    for (const [v, color] of Object.entries(PTR_COLORS)) {
      if (v in locs && v !== arrName) {
        const iv = parseInt(locs[v], 10);
        if (!isNaN(iv) && iv >= 0 && iv < n) {
          (ptrs[iv] = ptrs[iv] || []).push({ name: v, color });
        }
      }
    }

    // Swap detection
    const swapSet = new Set();
    if (prevArr && prevArr.length === n) {
      const diff = arr.reduce((a, v, i) => v !== prevArr[i] ? [...a, i] : a, []);
      if (diff.length === 2 &&
          arr[diff[0]] === prevArr[diff[1]] && arr[diff[1]] === prevArr[diff[0]]) {
        diff.forEach(i => swapSet.add(i));
      }
    }

    const ptrSet = new Set(Object.keys(ptrs).map(Number));

    // ── Comparison zone (face-to-face) ────────────────────────────────────
    let cmpZoneHtml = '';
    if (ptrSet.size >= 2 && swapSet.size === 0) {
      const idxs = [...ptrSet].sort((a, b) => a - b);
      const a = idxs[0], b = idxs[1];
      if (a < n && b < n) {
        cmpZoneHtml = `
        <div class="cmp-zone">
          <div class="cmp-elem">
            <div class="cmp-box">${fmtVal(arr[a])}</div>
            <div class="cmp-sub">arr[${a}]</div>
          </div>
          <div class="cmp-vs">VS</div>
          <div class="cmp-elem">
            <div class="cmp-box">${fmtVal(arr[b])}</div>
            <div class="cmp-sub">arr[${b}]</div>
          </div>
        </div>
        <div class="cmp-question">Is arr[${a}] = ${fmtVal(arr[a])}  &gt;  arr[${b}] = ${fmtVal(arr[b])} ?</div>`;
      }
    }

    // ── Array boxes ───────────────────────────────────────────────────────
    const boxSize = Math.max(34, Math.min(70, Math.floor((560 - (n-1)*6) / n)));
    const cells = Array.from({ length: n }, (_, i) => {
      const isSwap = swapSet.has(i);
      const isPtr  = ptrSet.has(i);
      const isCmp  = ptrSet.size >= 2 && isPtr && !isSwap;
      const isErr  = (step.event === 'error' || !!step.error) && isPtr;

      let state = 'state-default';
      if (isErr)       state = 'state-error';
      else if (isSwap) state = 'state-swap';
      else if (isCmp)  state = 'state-cmp';
      else if (isPtr)  state = 'state-active';

      const arrowsHtml = (ptrs[i] || []).map(({ name, color }) => `
        <div class="arr-ptr">
          <div class="ptr-arrow" style="color:${color}">▲</div>
          <div class="ptr-label" style="color:${color}">${esc(name)}</div>
        </div>`).join('');

      const sStyle = `width:${boxSize}px;height:${boxSize}px;font-size:${boxSize>=55?'1.05rem':'.82rem'}`;

      return `
      <div class="arr-cell">
        <div class="arr-idx">${i}</div>
        <div class="arr-box ${state}" style="${sStyle}">${fmtVal(arr[i])}</div>
        ${arrowsHtml}
      </div>`;
    }).join('');

    // ── Operation label ───────────────────────────────────────────────────
    let opHtml = '';
    if (swapSet.size === 2) {
      const [a, b] = [...swapSet].sort((x,y)=>x-y);
      opHtml = `<div class="op-label swap-op">🔄 SWAP  arr[${a}]=${fmtVal(arr[a])}  ↔  arr[${b}]=${fmtVal(arr[b])}</div>`;
    } else if (ptrSet.size >= 2 && !cmpZoneHtml) {
      const [a, b] = [...ptrSet].sort((x,y)=>x-y);
      opHtml = `<div class="op-label cmp-op">🔍 Comparing  arr[${a}]=${fmtVal(arr[a])}  vs  arr[${b}]=${fmtVal(arr[b])}</div>`;
    }

    el.innerHTML = `
      <div class="arr-label">${esc(arrName)}  [ length = ${n} ]</div>
      ${cmpZoneHtml}
      <div class="box-row">${cells}</div>
      ${opHtml}`;
  }

  // ── Variables panel ─────────────────────────────────────────────────────────
  _renderVars(locs, prevLocs) {
    const el = this.els.varsEl;
    if (!el) return;
    const rows = [];
    for (const [k, v] of Object.entries(locs)) {
      if (k.startsWith('__')) continue;
      const changed  = prevLocs[k] !== undefined && String(prevLocs[k]) !== String(v);
      const isResult = RESULT_VARS.has(k);
      const vStr     = String(v).length > 36 ? String(v).slice(0,35) + '…' : String(v);
      rows.push(`
        <div class="var-row${changed?' var-changed':''}${isResult?' var-result':''}">
          <span class="var-key">${esc(k)}</span>
          <span class="var-eq"> = </span>
          <span class="var-val" title="${esc(String(v))}">${esc(vStr)}</span>
          ${changed ? `<span class="var-changed-badge">↑ changed</span>` : ''}
        </div>`);
    }
    el.innerHTML = rows.length ? rows.join('') : '<div class="stack-empty">No variables yet</div>';
  }

  // ── Explanation ─────────────────────────────────────────────────────────────
  _renderExplain(step, prevStep) {
    const el = this.els.explainEl;
    if (!el) return;

    const text = step.explanation || this._genExplain(step, prevStep);
    const ev   = step.event;
    const icon = step.error || ev === 'exception' ? '🔴'
               : ev === 'call'   ? '📞'
               : ev === 'return' ? '↩️'
               : '▶️';

    const cls  = step.error || ev === 'exception' ? 'explain-error'
               : ev === 'call'   ? 'explain-call'
               : ev === 'return' ? 'explain-return'
               : 'explain-line';

    el.className = `explain-box ${cls}`;
    el.innerHTML =
      `<span class="explain-icon">${icon}</span>` +
      `<span class="explain-text">${esc(text)}</span>`;
  }

  _genExplain(step, prevStep) {
    const locs     = step.locals || {};
    const prevLocs = prevStep ? prevStep.locals || {} : {};
    const cl       = (this.lines[(step.line || 1) - 1] || '').trim();
    const ev       = step.event;

    if (step.error) return `Error: ${step.error}`;

    if (ev === 'call') {
      const fn = (step.stack || []).slice(-1)[0] || 'function';
      return `Entering function "${fn}" — control jumps to its body.`;
    }
    if (ev === 'return') {
      const fn = (step.stack || []).slice(-1)[0] || 'function';
      return `Returning from "${fn}" — going back to the calling location.`;
    }

    // Variable changes
    for (const [k, v] of Object.entries(locs)) {
      if (k.startsWith('__')) continue;
      if (prevLocs[k] !== undefined && String(prevLocs[k]) !== String(v)) {
        if (RESULT_VARS.has(k))
          return `✅ "${k}" updated to ${v} — this is the new best value found so far.`;
        const diff = _arrDiff(String(prevLocs[k]), String(v));
        if (diff) return `🔄 Array "${k}" changed — ${diff}.`;
        return `📝 Variable "${k}" changed from ${prevLocs[k]} → ${v}.`;
      }
    }

    // Code-line based
    if (/^(if|elif)\s/.test(cl))
      return `🔍 Checking condition: ${cl.replace(/^(if|elif)\s/,'').replace(/:$/,'')} — is this True or False?`;
    if (/^else/.test(cl))
      return '↪️ The condition above was False — we take the else branch.';
    if (/^(for|while)\s/.test(cl))
      return `🔄 Loop iteration: ${cl.replace(/:$/,'')}`;
    if (/^return\s/.test(cl))
      return `↩️ Returning: ${cl.replace(/^return\s/,'')}`;
    if (/print\s*\(|cout|printf|console\.log/.test(cl))
      return '🖨️ This line prints output to the console.';
    if (/[^=!<>]=[^=]/.test(cl))
      return `📌 Assignment: ${cl} — storing a value into a variable.`;

    return `▶️ Executing line ${step.line}: ${cl || '…'}`;
  }

  // ── Call stack ──────────────────────────────────────────────────────────────
  _renderStack(stack) {
    const el = this.els.stackEl;
    if (!el) return;
    if (!stack.length) {
      el.innerHTML = '<div class="stack-empty">— empty —</div>';
      return;
    }
    el.innerHTML = [...stack].reverse()
      .map((fn, i) =>
        `<div class="stack-frame${i===0?' stack-top':''}">${esc(fn)}()</div>`)
      .join('');
  }

  // ── Output ───────────────────────────────────────────────────────────────────
  _renderOutput(stdout) {
    const area = this.els.outputAreaEl;
    const text = this.els.outputEl;
    if (!area || !text) return;
    if (stdout.trim()) {
      area.classList.remove('hidden');
      text.textContent = stdout;
    } else {
      area.classList.add('hidden');
    }
  }

  // ── Step meta ────────────────────────────────────────────────────────────────
  _updateMeta() {
    const pct = ((this.cur + 1) / this.steps.length) * 100;
    if (this.els.progressEl)  this.els.progressEl.style.width = pct + '%';
    if (this.els.stepCountEl)
      this.els.stepCountEl.textContent = `Step ${this.cur + 1} / ${this.steps.length}`;
  }

  // ── Playback controls ────────────────────────────────────────────────────────
  play() {
    if (this.playing) return;
    this.playing = true;
    const ms = Math.max(80, Math.round(1600 / this.speed));
    this._timer = setInterval(() => {
      if (this.cur < this.steps.length - 1) {
        this.goTo(this.cur + 1);
      } else {
        this.pause();
        if (this._onEnd) this._onEnd();
      }
    }, ms);
  }

  pause() {
    this.playing = false;
    clearInterval(this._timer);
    this._timer = null;
  }

  next()    { this.pause(); if (this.cur < this.steps.length - 1) this.goTo(this.cur + 1); }
  prev()    { this.pause(); if (this.cur > 0) this.goTo(this.cur - 1); }
  first()   { this.pause(); this.goTo(0); }
  last()    { this.pause(); this.goTo(this.steps.length - 1); }
  setSpeed(s) { this.speed = s; if (this.playing) { this.pause(); this.play(); } }
  isPlaying() { return this.playing; }
}

// ── Array diff helper ─────────────────────────────────────────────────────────
function _arrDiff(oldStr, newStr) {
  try {
    const o = JSON.parse(oldStr.replace(/'/g, '"'));
    const n = JSON.parse(newStr.replace(/'/g, '"'));
    if (!Array.isArray(o) || !Array.isArray(n) || o.length !== n.length) return null;
    const diff = o.reduce((a, v, i) => v !== n[i] ? [...a, i] : a, []);
    if (diff.length === 2 &&
        o[diff[0]] === n[diff[1]] && o[diff[1]] === n[diff[0]])
      return `positions [${diff[0]}] and [${diff[1]}] were SWAPPED`;
    if (diff.length) return `position[s] [${diff.join(', ')}] updated`;
  } catch {}
  return null;
}

// Make accessible globally
window.TraceVisualizer = TraceVisualizer;
