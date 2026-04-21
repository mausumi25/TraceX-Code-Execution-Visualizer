'use strict';
/**
 * visualizer.js — Interactive Step-by-Step Code Visualizer Engine
 *
 * Renders execution steps as live animations in the browser.
 * Features:
 *   - Array boxes with colour-coded states (compare, swap, sorted, found, error)
 *   - Face-to-face comparison display
 *   - Swap animation with arrows
 *   - Variable panel with change highlighting
 *   - Call stack display
 *   - Play/Pause/Next/Prev/Speed controls
 *   - Step scrubber (seek bar)
 *   - Beginner-friendly explanation per step
 */

// ── Constants ─────────────────────────────────────────────────────────────────
const PTR_COLORS = {
  i:'#e3b341', j:'#d29922', k:'#bc8cff', l:'#58a6ff', r:'#f85149',
  low:'#58a6ff', high:'#f85149', mid:'#bc8cff',
  left:'#58a6ff', right:'#f85149', start:'#58a6ff', end:'#f85149',
  pivot:'#f778ba', slow:'#3fb950', fast:'#79c0ff',
  p:'#e3b341', q:'#d29922', curr:'#3fb950', prev:'#58a6ff',
  ans:'#3fb950', idx:'#e3b341', pos:'#e3b341',
  min_idx:'#3fb950', max_idx:'#f85149',
};

const RESULT_VARS = new Set([
  'max','min','result','ans','maximum','minimum',
  'largest','smallest','max_val','min_val','res',
  'found','flag','count','total','sum','product','output','key','val','value',
]);

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function tryParseNumList(s) {
  if (typeof s !== 'string') return null;
  s = s.replace(/[…]{1,}|\.\.\./g,'').trim();
  if (!s.startsWith('[') || !s.endsWith(']')) return null;
  try {
    const arr = JSON.parse(s.replace(/'/g,'"'));
    if (Array.isArray(arr) && arr.length >= 2 &&
        arr.every(x => typeof x === 'number')) return arr;
  } catch {}
  return null;
}

function fmtVal(v) {
  if (typeof v === 'number' && Number.isInteger(v)) return String(v);
  if (typeof v === 'number') return v.toFixed(2);
  const s = String(v);
  return s.length > 28 ? s.slice(0,27)+'…' : s;
}

function arrayDiff(oldStr, newStr) {
  try {
    const o = JSON.parse(String(oldStr).replace(/'/g,'"'));
    const n = JSON.parse(String(newStr).replace(/'/g,'"'));
    if (!Array.isArray(o)||!Array.isArray(n)||o.length!==n.length) return null;
    const diff = o.map((_,i)=>i).filter(i=>o[i]!==n[i]);
    if (diff.length===2 && o[diff[0]]===n[diff[1]] && o[diff[1]]===n[diff[0]])
      return {type:'swap', a:diff[0], b:diff[1], va:n[diff[0]], vb:n[diff[1]]};
    if (diff.length) return {type:'change', indices:diff};
  } catch {}
  return null;
}

// ── Main class ────────────────────────────────────────────────────────────────
class TraceVisualizer {
  /**
   * @param {Object} opts
   * @param {Array}  opts.steps      — step objects from backend
   * @param {Array}  opts.codeLines  — source code split by line
   * @param {string} opts.language   — e.g. "python"
   * @param {string} opts.algoName   — detected algorithm name
   * @param {Object} opts.els        — { codeEl, dsEl, opEl, opIconEl, opTextEl,
   *                                    outputEl, outputTextEl,
   *                                    explainEl, varsEl, stackEl,
   *                                    stepCountEl, ctrlStepEl, progressEl,
   *                                    scrubberEl, playBtn }
   */
  constructor(opts) {
    this.steps     = opts.steps;
    this.codeLines = opts.codeLines;
    this.language  = (opts.language||'python').toUpperCase();
    this.algoName  = opts.algoName || 'Algorithm Execution';
    this.els       = opts.els;

    this.cur      = 0;
    this.playing  = false;
    this.speed    = 1;      // steps per second
    this._timer   = null;
    this._prevLoc = {};

    this._buildCode();
    if (this.steps.length) this.goTo(0);
  }

  // ── Code panel ───────────────────────────────────────────────────────────────
  _buildCode() {
    const el = this.els.codeEl;
    if (!el) return;
    el.innerHTML = '';
    this.codeLines.forEach((line, i) => {
      const row         = document.createElement('div');
      row.className     = 'code-line';
      row.dataset.ln    = i + 1;
      const gutter      = document.createElement('span');
      gutter.className  = 'code-gutter';
      gutter.textContent= i + 1;
      const text        = document.createElement('span');
      text.className    = 'code-text';
      text.textContent  = line || ' ';
      row.appendChild(gutter);
      row.appendChild(text);
      el.appendChild(row);
    });
  }

  _hl(lineNo, isErr) {
    const el = this.els.codeEl;
    if (!el) return;
    el.querySelectorAll('.code-line').forEach(r => {
      r.classList.remove('active','error-line');
    });
    const target = el.querySelector(`[data-ln="${lineNo}"]`);
    if (!target) return;
    target.classList.add(isErr ? 'error-line' : 'active');
    target.scrollIntoView({block:'nearest', behavior:'smooth'});
  }

  // ── Go to step ────────────────────────────────────────────────────────────────
  goTo(idx) {
    if (idx < 0) idx = 0;
    if (idx >= this.steps.length) idx = this.steps.length - 1;
    this.cur = idx;

    const step    = this.steps[idx];
    const prev    = idx > 0 ? this.steps[idx-1] : null;
    const locs    = step.locals || {};
    const prevLoc = prev ? (prev.locals || {}) : {};
    const isErr   = step.event === 'error' || step.event === 'exception' || !!step.error;

    this._hl(step.line, isErr);
    this._renderDS(step, prev, locs, prevLoc);
    this._renderExplain(step, prev);
    this._renderVars(locs, prevLoc);
    this._renderStack(step.stack || []);
    this._renderOutput(step);
    this._updateMeta();

    this._prevLoc = locs;
  }

  // ── Data structure render ────────────────────────────────────────────────────
  _renderDS(step, prev, locs, prevLoc) {
    // Find largest numeric array
    let arrName = null, arr = null;
    for (const [k, v] of Object.entries(locs)) {
      const p = tryParseNumList(String(v));
      if (p && (!arr || p.length > arr.length)) { arrName=k; arr=p; }
    }

    const dsEl = this.els.dsEl;
    const opEl = this.els.opEl;

    if (!arr) {
      // No array — hide op box, show nothing special
      if (dsEl) dsEl.innerHTML = '<div class="ds-placeholder">No array detected in current scope</div>';
      if (opEl) opEl.classList.add('hidden');
      return;
    }

    // Find previous array for diff
    let prevArr = null;
    if (prev) {
      const pv = (prev.locals||{})[arrName];
      if (pv) prevArr = tryParseNumList(String(pv));
    }

    // Detect diff (swap / change)
    const diff = prevArr ? arrayDiff(String(prevArr), String(arr)) : null;
    const swapSet = new Set(diff && diff.type==='swap' ? [diff.a, diff.b] : []);

    // Pointer positions
    const ptrs = {};
    for (const [v, color] of Object.entries(PTR_COLORS)) {
      if (v in locs && v !== arrName) {
        const iv = parseInt(locs[v], 10);
        if (!isNaN(iv) && iv >= 0 && iv < arr.length) {
          if (!ptrs[iv]) ptrs[iv] = [];
          ptrs[iv].push({v, color});
        }
      }
    }
    const ptrSet = new Set(Object.keys(ptrs).map(Number));
    const isCmp  = ptrSet.size >= 2;

    // Build array DOM
    const wrap    = document.createElement('div');
    wrap.className= 'array-wrap';

    const lbl        = document.createElement('div');
    lbl.className    = 'arr-label';
    lbl.textContent  = `${arrName}   [ n = ${arr.length} ]`;
    wrap.appendChild(lbl);

    // If comparing 2 elements, show big face-to-face view above the array
    if (isCmp && !swapSet.size) {
      const idxs = [...ptrSet].sort((a,b)=>a-b);
      const a = idxs[0], b = idxs[1];
      wrap.appendChild(this._makeCmpFace(a, arr[a], b, arr[b]));
    }

    if (swapSet.size === 2) {
      const idxs = [...swapSet];
      wrap.appendChild(this._makeSwapFace(idxs[0], arr[idxs[0]], idxs[1], arr[idxs[1]]));
    }

    // All boxes
    const boxRow    = document.createElement('div');
    boxRow.className= 'box-row';

    const isErr = !!step.error;

    for (let i = 0; i < arr.length; i++) {
      const cell      = document.createElement('div');
      cell.className  = 'arr-cell';

      const idx       = document.createElement('div');
      idx.className   = 'arr-idx';
      idx.textContent = i;
      cell.appendChild(idx);

      const box       = document.createElement('div');
      box.className   = 'arr-box';
      const isPtr     = ptrSet.has(i);
      const isCmpBox  = isCmp && isPtr;

      if      (isErr && isPtr)    box.classList.add('state-error');
      else if (swapSet.has(i))    box.classList.add('state-swap');
      else if (isCmpBox)          box.classList.add('state-cmp');
      else if (isPtr)             box.classList.add('state-active');
      else                        box.classList.add('state-default');

      box.textContent = fmtVal(arr[i]);
      cell.appendChild(box);

      // Pointer arrow(s) below
      if (ptrs[i]) {
        ptrs[i].forEach(({v, color}) => {
          const arrow        = document.createElement('div');
          arrow.className    = 'arr-ptr';
          arrow.innerHTML    = `<div class="ptr-arrow" style="color:${color}">▲</div>`
                             + `<div class="ptr-label" style="color:${color}">${esc(v)}</div>`;
          cell.appendChild(arrow);
        });
      }

      boxRow.appendChild(cell);
    }
    wrap.appendChild(boxRow);

    if (dsEl) {
      dsEl.innerHTML = '';
      dsEl.appendChild(wrap);
    }

    // Operation box text
    this._showOpBox(step, arr, ptrSet, diff, swapSet);
  }

  _makeCmpFace(a, va, b, vb) {
    const face      = document.createElement('div');
    face.className  = 'cmp-face';
    face.innerHTML  =
      `<div class="cmp-box-wrap">
        <div class="cmp-big-box">${esc(va)}</div>
        <div class="cmp-lbl">arr[${a}]</div>
      </div>
      <div class="cmp-vs">VS</div>
      <div class="cmp-box-wrap">
        <div class="cmp-big-box">${esc(vb)}</div>
        <div class="cmp-lbl">arr[${b}]</div>
      </div>`;
    const q       = document.createElement('div');
    q.className   = 'cmp-question';
    q.textContent = `Is ${va} > ${vb} ?`;
    const wrap    = document.createElement('div');
    wrap.appendChild(face);
    wrap.appendChild(q);
    return wrap;
  }

  _makeSwapFace(a, va, b, vb) {
    const face     = document.createElement('div');
    face.className = 'swap-face';
    face.innerHTML =
      `<div class="cmp-box-wrap">
        <div class="swap-big-box">${esc(va)}</div>
        <div class="cmp-lbl">arr[${a}]</div>
      </div>
      <div class="swap-arrow">⇄</div>
      <div class="cmp-box-wrap">
        <div class="swap-big-box">${esc(vb)}</div>
        <div class="cmp-lbl">arr[${b}]</div>
      </div>`;
    return face;
  }

  _showOpBox(step, arr, ptrSet, diff, swapSet) {
    const opEl   = this.els.opEl;
    const iconEl = this.els.opIconEl;
    const textEl = this.els.opTextEl;
    if (!opEl) return;

    let icon='', text='';

    if (step.error) {
      icon = '🔴';
      text = `<strong>Error:</strong> ${esc(step.error)}`;
    } else if (swapSet.size === 2) {
      const [a,b] = [...swapSet];
      icon = '🔄';
      text = `<strong>SWAP!</strong>  arr[${a}] = <strong>${arr[a]}</strong>  ↔  arr[${b}] = <strong>${arr[b]}</strong>`;
    } else if (ptrSet.size >= 2) {
      const idxs = [...ptrSet].sort((a,b)=>a-b);
      const [a,b] = idxs;
      icon = '🔍';
      text = `Comparing  arr[${a}] = <strong>${arr[a]}</strong>  vs  arr[${b}] = <strong>${arr[b]}</strong>`;
    } else if (ptrSet.size === 1) {
      const i = [...ptrSet][0];
      icon = '▶';
      text = `Visiting  arr[${i}] = <strong>${arr[i]}</strong>`;
    } else {
      opEl.classList.add('hidden');
      return;
    }

    opEl.classList.remove('hidden');
    if (iconEl) iconEl.textContent = icon;
    if (textEl) textEl.innerHTML   = text;
  }

  // ── Explanation ──────────────────────────────────────────────────────────────
  _renderExplain(step, prev) {
    const el = this.els.explainEl;
    if (!el) return;

    const text = step.explanation || this._genExplanation(step, prev);
    const icon = _stepIcon(step);
    const ev   = step.event;

    el.innerHTML =
      `<span class="explain-icon">${icon}</span>` +
      `<span class="explain-text">${esc(text)}</span>`;

    el.className = 'viz-explain explain-box ';
    if      (ev==='error'||ev==='exception'||step.error) el.className += 'explain-error';
    else if (ev==='call')                                 el.className += 'explain-call';
    else if (ev==='return')                               el.className += 'explain-return';
    else                                                  el.className += 'explain-line';
  }

  _genExplanation(step, prev) {
    const locs    = step.locals || {};
    const prevLoc = prev ? (prev.locals||{}) : {};
    const line    = step.line;
    const cl      = (this.codeLines[line-1]||'').trim();
    const ev      = step.event;

    if (step.error)   return `Error: ${step.error}`;
    if (ev==='call')  { const fn=(step.stack||[]).slice(-1)[0]||'function'; return `Entering function "${fn}()".`; }
    if (ev==='return'){ const fn=(step.stack||[]).slice(-1)[0]||'function'; return `Returning from "${fn}()".`; }

    // Variable changes
    for (const [k,v] of Object.entries(locs)) {
      if (k.startsWith('__')) continue;
      const pv = prevLoc[k];
      if (pv!==undefined && String(pv)!==String(v)) {
        if (RESULT_VARS.has(k)) return `✅ "${k}" updated: ${pv} → ${v}. This is the current best value.`;
        const diff = arrayDiff(String(pv), String(v));
        if (diff?.type==='swap') return `🔄 Array "${k}" — positions [${diff.a}] and [${diff.b}] were swapped! (${diff.va} ↔ ${diff.vb})`;
        return `Variable "${k}" changed from ${pv} → ${v}.`;
      }
    }
    // Code-line hints
    if (/^(if |elif )/.test(cl)) return `🔍 Checking: ${cl}`;
    if (/^else/.test(cl))        return '↪️ Condition was False — taking the else branch.';
    if (/^for /.test(cl))        return `🔄 Loop: ${cl}`;
    if (/^while /.test(cl))      return `🔄 While check: ${cl}`;
    if (/^return /.test(cl))     return `↩️ Returning: ${cl}`;
    if (/print\(|cout/.test(cl)) return '🖨️ Printing output to the console.';
    if (/=/.test(cl)&&!/==/.test(cl)) return `📌 Assignment: ${cl}`;
    return `▶️ Executing line ${line}: ${cl||'…'}`;
  }

  // ── Variables ────────────────────────────────────────────────────────────────
  _renderVars(locs, prevLoc) {
    const el = this.els.varsEl;
    if (!el) return;
    const frag = document.createDocumentFragment();
    for (const [k,v] of Object.entries(locs)) {
      if (k.startsWith('__')) continue;
      const changed  = prevLoc[k]!==undefined && String(prevLoc[k])!==String(v);
      const isResult = RESULT_VARS.has(k);
      const row      = document.createElement('div');
      row.className  = `var-row${changed?' var-changed':''}${isResult?' var-result':''}`;

      const kEl  = document.createElement('span'); kEl.className='var-key';  kEl.textContent=k;
      const eqEl = document.createElement('span'); eqEl.className='var-eq';  eqEl.textContent=' = ';
      const vEl  = document.createElement('span'); vEl.className='var-val';
      vEl.textContent = fmtVal(v);
      if (changed) vEl.title=`was: ${prevLoc[k]}`;

      row.appendChild(kEl); row.appendChild(eqEl); row.appendChild(vEl);
      if (changed) {
        const b=document.createElement('span');
        b.className='var-changed-badge'; b.textContent='changed';
        row.appendChild(b);
      }
      frag.appendChild(row);
    }
    el.innerHTML='';
    el.appendChild(frag);
  }

  // ── Call stack ────────────────────────────────────────────────────────────────
  _renderStack(stack) {
    const el = this.els.stackEl;
    if (!el) return;
    if (!stack||!stack.length) {
      el.innerHTML='<div class="stack-empty">— empty —</div>'; return;
    }
    el.innerHTML = [...stack].reverse().map((fn,i)=>
      `<div class="stack-frame${i===0?' stack-top':''}">${esc(fn)}()</div>`
    ).join('');
  }

  // ── Output ────────────────────────────────────────────────────────────────────
  _renderOutput(step) {
    const boxEl  = this.els.outputEl;
    const textEl = this.els.outputTextEl;
    if (!boxEl||!textEl) return;
    const out = (step.stdout||'').trim();
    if (out) {
      boxEl.classList.remove('hidden');
      textEl.textContent = out;
    } else {
      boxEl.classList.add('hidden');
    }
  }

  // ── Meta (step counter, progress, scrubber) ───────────────────────────────────
  _updateMeta() {
    const n = this.steps.length;
    const i = this.cur + 1;
    const txt = `Step ${i} / ${n}`;
    if (this.els.stepCountEl)  this.els.stepCountEl.textContent  = txt;
    if (this.els.ctrlStepEl)   this.els.ctrlStepEl.textContent   = txt;
    if (this.els.progressEl)   this.els.progressEl.style.width   = (i/n*100)+'%';
    if (this.els.scrubberEl) {
      this.els.scrubberEl.max   = n - 1;
      this.els.scrubberEl.value = this.cur;
    }
    // Prev / next buttons
    const {playBtn} = this.els;
    if (playBtn) {
      playBtn.classList.toggle('playing', this.playing);
      playBtn.textContent = this.playing ? '⏸' : '▶';
    }
  }

  // ── Playback controls ────────────────────────────────────────────────────────
  play() {
    if (this.playing) return;
    this.playing = true;
    const ms = Math.max(80, 1800/this.speed);
    this._timer = setInterval(()=>{
      if (this.cur < this.steps.length-1) this.goTo(this.cur+1);
      else                                this.pause();
    }, ms);
    this._updateMeta();
  }

  pause() {
    if (!this.playing) return;
    this.playing = false;
    clearInterval(this._timer); this._timer=null;
    this._updateMeta();
  }

  toggle() { this.playing ? this.pause() : this.play(); }
  next()   { this.pause(); this.goTo(this.cur+1); }
  prev()   { this.pause(); this.goTo(this.cur-1); }
  first()  { this.pause(); this.goTo(0); }
  last()   { this.pause(); this.goTo(this.steps.length-1); }
  seekTo(n){ this.pause(); this.goTo(n); }
  setSpeed(s){ this.speed=s; if (this.playing){this.pause();this.play();} }
  isPlaying(){ return this.playing; }
}

// ── Step icon helper ──────────────────────────────────────────────────────────
function _stepIcon(step) {
  const ev = step.event;
  if (ev==='error'||step.error) return '🔴';
  if (ev==='exception')         return '⚠️';
  if (ev==='call')              return '📞';
  if (ev==='return')            return '↩️';
  return '▶️';
}

// Export to global
window.TraceVisualizer = TraceVisualizer;
