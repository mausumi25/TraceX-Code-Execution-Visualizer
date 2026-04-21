'use strict';
/**
 * main.js — App Orchestration
 * Wires language selection, code type, editor, custom input,
 * API call, and the interactive TraceVisualizer together.
 */

// ── DOM refs ──────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// Nav
const langPills      = document.querySelectorAll('.lang-pill');
const themeToggle    = $('theme-toggle');

// Setup
const typeComplete   = $('type-complete');
const typeCompLabel  = $('type-complete-label');
const typeLeetcode   = $('type-leetcode');
const typeLCLabel    = $('type-leetcode-label');
const typeHint       = $('type-hint');

const codeEditor     = $('code-editor');
const lineNums       = $('line-nums');
const runBtn         = $('run-btn');
const clearBtn       = $('clear-btn');
const sampleBtn      = $('sample-btn');
const customInput    = $('custom-input');
const clearInputBtn  = $('clear-input-btn');

// Panels
const setupPanel     = $('setup-panel');
const errorPanel     = $('error-panel');
const loadingPanel   = $('loading-panel');
const vizPanel       = $('viz-panel');

// Error
const errKind        = $('err-kind');
const errMsg         = $('err-msg');
const errLoc         = $('err-loc');
const errDismiss     = $('err-dismiss');

// Loading
const loadingMsg     = $('loading-msg');

// Visualizer
const backBtn        = $('back-btn');
const vizAlgoName    = $('viz-algo-name');
const vizLangBadge   = $('viz-lang-badge');
const vizStepCount   = $('viz-step-count');
const downloadVideoBtn = $('download-video-btn');

const runtimeBanner  = $('runtime-banner');
const rebMsg         = $('reb-msg');
const rebClose       = $('reb-close');

const vizCode        = $('viz-code');
const vizDs          = $('viz-ds');
const vizOpBox       = $('viz-op-box');
const vizOpIcon      = $('viz-op-icon');
const vizOpText      = $('viz-op-text');
const vizOutputBox   = $('viz-output-box');
const vizOutputText  = $('viz-output-text');
const vizExplain     = $('viz-explain');
const vizVars        = $('viz-vars');
const vizStack       = $('viz-stack');
const vizProgressFill= $('viz-progress-fill');
const stepScrubber   = $('step-scrubber');
const ctrlStepInfo   = $('ctrl-step-info');

// Controls
const ctrlFirst      = $('ctrl-first');
const ctrlPrev       = $('ctrl-prev');
const ctrlPlay       = $('ctrl-play');
const ctrlNext       = $('ctrl-next');
const ctrlLast       = $('ctrl-last');
const speedSelect    = $('speed-select');

// ── State ─────────────────────────────────────────────────────────────────────
let currentLang      = 'python';
let currentCodeType  = 'complete';
let visualizer       = null;
let lastVideoUrl     = null;

// SAMPLES (shown for each language)
const SAMPLES = {
  python: `# Find the largest number
arr = [64, 34, 25, 12, 22, 11, 90]
max_val = arr[0]
for i in range(1, len(arr)):
    if arr[i] > max_val:
        max_val = arr[i]
print("Largest:", max_val)`,

  javascript: `// Bubble Sort
let arr = [64, 34, 25, 12, 22];
let n = arr.length;
for (let i = 0; i < n-1; i++) {
  for (let j = 0; j < n-i-1; j++) {
    if (arr[j] > arr[j+1]) {
      let t = arr[j]; arr[j]=arr[j+1]; arr[j+1]=t;
    }
  }
}
console.log(arr);`,

  c: `#include <stdio.h>
int main() {
    int arr[] = {64, 34, 25, 12, 90};
    int n = 5, max_val = arr[0];
    for (int i = 1; i < n; i++)
        if (arr[i] > max_val) max_val = arr[i];
    printf("Largest: %d\\n", max_val);
    return 0;
}`,

  cpp: `#include <iostream>
#include <vector>
using namespace std;
int main() {
    vector<int> arr = {64, 34, 25, 12, 90};
    int n = arr.size(), max_val = arr[0];
    for (int i = 1; i < n; i++)
        if (arr[i] > max_val) max_val = arr[i];
    cout << "Largest: " << max_val << endl;
    return 0;
}`,
};

const LEETCODE_SAMPLES = {
  python: `def twoSum(self, nums, target):
    seen = {}
    for i, n in enumerate(nums):
        diff = target - n
        if diff in seen:
            return [seen[diff], i]
        seen[n] = i
    return []`,
  javascript: `var twoSum = function(nums, target) {
  const seen = {};
  for (let i = 0; i < nums.length; i++) {
    const diff = target - nums[i];
    if (seen[diff] !== undefined) return [seen[diff], i];
    seen[nums[i]] = i;
  }
};`,
  cpp: `class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int,int> seen;
        for (int i = 0; i < nums.size(); i++) {
            int diff = target - nums[i];
            if (seen.count(diff)) return {seen[diff], i};
            seen[nums[i]] = i;
        }
        return {};
    }
};`,
  c: `// LeetCode C — Complete program is required\nint main() { return 0; }`,
};

// ── Theme ─────────────────────────────────────────────────────────────────────
(function () {
  const stored = localStorage.getItem('trace-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', stored);
  if (themeToggle) themeToggle.textContent = stored==='dark' ? '🌙' : '☀️';
})();

if (themeToggle) {
  themeToggle.addEventListener('click', () => {
    const cur  = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = cur==='dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('trace-theme', next);
    themeToggle.textContent = next==='dark' ? '🌙' : '☀️';
  });
}

// ── Language selection ────────────────────────────────────────────────────────
langPills.forEach(btn => {
  btn.addEventListener('click', () => {
    langPills.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentLang = btn.dataset.lang;
    // Only load sample if editor is empty or has previous sample
    const lines = (codeEditor.value||'').trim().split('\n').length;
    if (lines <= 1) loadSample();
  });
});

// ── Code type toggle ──────────────────────────────────────────────────────────
[typeComplete, typeLeetcode].forEach(radio => {
  if (!radio) return;
  radio.addEventListener('change', () => {
    currentCodeType = radio.value;
    const isLC = currentCodeType === 'leetcode';
    typeCompLabel?.classList.toggle('active', !isLC);
    typeLCLabel?.classList.toggle('active', isLC);
    if (typeHint) {
      typeHint.textContent = isLC
        ? 'Paste your function/class — main() injected automatically'
        : 'Include main() / top-level code';
    }
    loadSample();
  });
});

// ── Line numbers sync ─────────────────────────────────────────────────────────
function updateLineNums() {
  if (!lineNums || !codeEditor) return;
  const lines = (codeEditor.value + '\n').split('\n').length - 1;
  lineNums.innerHTML = Array.from({length:lines},(_,i)=>i+1).join('\n');
}

if (codeEditor) {
  updateLineNums();
  codeEditor.addEventListener('input', updateLineNums);
  codeEditor.addEventListener('scroll', () => {
    if (lineNums) lineNums.scrollTop = codeEditor.scrollTop;
  });
  // Tab key support
  codeEditor.addEventListener('keydown', e => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const s = codeEditor.selectionStart;
      const v = codeEditor.value;
      codeEditor.value = v.slice(0,s) + '    ' + v.slice(codeEditor.selectionEnd);
      codeEditor.selectionStart = codeEditor.selectionEnd = s + 4;
      updateLineNums();
    }
  });
}

// ── Sample / Clear ────────────────────────────────────────────────────────────
function loadSample() {
  if (!codeEditor) return;
  const map = currentCodeType === 'leetcode' ? LEETCODE_SAMPLES : SAMPLES;
  codeEditor.value = map[currentLang] || map['python'];
  updateLineNums();
  hideError();
}

if (sampleBtn) sampleBtn.addEventListener('click', loadSample);

if (clearBtn) {
  clearBtn.addEventListener('click', () => {
    if (codeEditor) { codeEditor.value=''; updateLineNums(); }
    hideError();
  });
}
if (clearInputBtn) {
  clearInputBtn.addEventListener('click', () => {
    if (customInput) customInput.value='';
  });
}

// ── Error helpers ─────────────────────────────────────────────────────────────
function showError(kind, msg, loc='') {
  if (errKind) errKind.textContent = kind;
  if (errMsg)  errMsg.textContent  = msg;
  if (errLoc)  errLoc.textContent  = loc;
  errorPanel?.classList.remove('hidden');
}
function hideError() {
  errorPanel?.classList.add('hidden');
}
if (errDismiss) errDismiss.addEventListener('click', hideError);

// ── Loading helpers ───────────────────────────────────────────────────────────
const LOAD_MSGS = [
  'Checking syntax…',
  'Running step-by-step trace…',
  'Building execution steps…',
  'Almost there…',
];
let _loadTimer = null;

function showLoading() {
  loadingPanel?.classList.remove('hidden');
  let mi = 0;
  if (loadingMsg) loadingMsg.textContent = LOAD_MSGS[0];
  _loadTimer = setInterval(()=>{
    mi = Math.min(mi+1, LOAD_MSGS.length-1);
    if (loadingMsg) loadingMsg.textContent = LOAD_MSGS[mi];
  }, 1200);
}
function hideLoading() {
  clearInterval(_loadTimer);
  loadingPanel?.classList.add('hidden');
}

// ── Show / hide panels ────────────────────────────────────────────────────────
function showSetup() {
  setupPanel?.classList.remove('hidden');
  vizPanel?.classList.add('hidden');
}

function showViz() {
  setupPanel?.classList.add('hidden');
  vizPanel?.classList.remove('hidden');
}

// ── Run trace ─────────────────────────────────────────────────────────────────
async function runTrace() {
  const code = (codeEditor?.value || '').trim();
  if (!code) { showError('No Code', 'Please write or paste some code first.'); return; }

  hideError();
  showLoading();
  if (runBtn) runBtn.disabled = true;

  try {
    const resp = await fetch('/api/trace', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        code,
        language:  currentLang,
        code_type: currentCodeType,
        stdin:     customInput?.value || '',
        make_video: false,
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(()=>({}));
      throw new Error(err.error || `Server error ${resp.status}`);
    }

    const data = await resp.json();
    hideLoading();

    // Syntax error — don't show viz
    if (data.syntax_error) {
      const line = data.error_line ? ` (line ${data.error_line})` : '';
      showError('Syntax Error', data.error, line);
      return;
    }

    if (!data.steps || !data.steps.length) {
      showError('No Steps', 'The tracer produced no execution steps.');
      return;
    }

    // Show visualizer
    renderVisualizer(data);

  } catch (err) {
    hideLoading();
    showError('Request Failed', err.message || 'Unknown error.');
  } finally {
    if (runBtn) runBtn.disabled = false;
  }
}

if (runBtn) runBtn.addEventListener('click', runTrace);

// ── Render visualizer ─────────────────────────────────────────────────────────
function renderVisualizer(data) {
  const steps     = data.steps;
  const codeLines = data.code_lines || (codeEditor.value||'').split('\n');
  const language  = data.language || currentLang;
  const algoName  = detectAlgoName(codeLines, language);

  lastVideoUrl = data.video_url || null;

  // Update header
  if (vizAlgoName)  vizAlgoName.textContent  = algoName;
  if (vizLangBadge) {
    vizLangBadge.textContent  = language.toUpperCase();
    vizLangBadge.style.background = LANG_COLORS[language.toLowerCase()] || '#58a6ff';
  }

  // Runtime error banner
  if (data.has_runtime_error && data.runtime_error_msg) {
    if (rebMsg) rebMsg.textContent = data.runtime_error_msg;
    runtimeBanner?.classList.remove('hidden');
  } else {
    runtimeBanner?.classList.add('hidden');
  }

  // Download button
  if (downloadVideoBtn) {
    downloadVideoBtn.style.display = 'inline-flex';
    downloadVideoBtn.onclick = () => requestVideoExport(data);
  }

  // Destroy old visualizer
  if (visualizer) { visualizer.pause(); visualizer = null; }

  // Create new visualizer
  visualizer = new TraceVisualizer({
    steps,
    codeLines,
    language,
    algoName,
    els: {
      codeEl:      vizCode,
      dsEl:        vizDs,
      opEl:        vizOpBox,
      opIconEl:    vizOpIcon,
      opTextEl:    vizOpText,
      outputEl:    vizOutputBox,
      outputTextEl:vizOutputText,
      explainEl:   vizExplain,
      varsEl:      vizVars,
      stackEl:     vizStack,
      stepCountEl: vizStepCount,
      ctrlStepEl:  ctrlStepInfo,
      progressEl:  vizProgressFill,
      scrubberEl:  stepScrubber,
      playBtn:     ctrlPlay,
    },
  });

  // Wire controls
  if (ctrlFirst) ctrlFirst.onclick = () => visualizer.first();
  if (ctrlPrev)  ctrlPrev.onclick  = () => visualizer.prev();
  if (ctrlPlay)  ctrlPlay.onclick  = () => visualizer.toggle();
  if (ctrlNext)  ctrlNext.onclick  = () => visualizer.next();
  if (ctrlLast)  ctrlLast.onclick  = () => visualizer.last();

  if (speedSelect) {
    speedSelect.onchange = () => visualizer.setSpeed(parseFloat(speedSelect.value));
  }
  if (stepScrubber) {
    stepScrubber.oninput = () => visualizer.seekTo(parseInt(stepScrubber.value, 10));
  }

  // Keyboard shortcuts
  document.onkeydown = e => {
    if (!vizPanel || vizPanel.classList.contains('hidden')) return;
    if (e.target === codeEditor || e.target === customInput) return;
    if (e.key === 'ArrowRight' || e.key === 'n') { e.preventDefault(); visualizer.next(); }
    if (e.key === 'ArrowLeft'  || e.key === 'p') { e.preventDefault(); visualizer.prev(); }
    if (e.key === ' ')  { e.preventDefault(); visualizer.toggle(); }
    if (e.key === 'Home') { e.preventDefault(); visualizer.first(); }
    if (e.key === 'End')  { e.preventDefault(); visualizer.last(); }
  };

  showViz();
}

// ── Back to editor ────────────────────────────────────────────────────────────
if (backBtn) {
  backBtn.addEventListener('click', () => {
    if (visualizer) { visualizer.pause(); }
    document.onkeydown = null;
    showSetup();
  });
}

if (rebClose) {
  rebClose.addEventListener('click', () => runtimeBanner?.classList.add('hidden'));
}

// ── Export video (optional, on demand) ───────────────────────────────────────
async function requestVideoExport(originalData) {
  if (lastVideoUrl) { window.open(lastVideoUrl, '_blank'); return; }

  downloadVideoBtn.disabled = true;
  downloadVideoBtn.textContent = '⏳ Generating…';

  try {
    const resp = await fetch('/api/trace', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        code:      codeEditor?.value || '',
        language:  currentLang,
        code_type: currentCodeType,
        stdin:     customInput?.value || '',
        make_video: true,
      }),
    });
    const data = await resp.json();
    if (data.video_url) {
      lastVideoUrl = data.video_url;
      const a = document.createElement('a');
      a.href = data.video_url; a.download='trace.mp4'; a.click();
    }
  } catch (err) {
    alert('Video export failed: ' + err.message);
  } finally {
    downloadVideoBtn.disabled = false;
    downloadVideoBtn.textContent = '⬇ Export Video';
  }
}

// ── Algorithm name detector (client-side) ─────────────────────────────────────
function detectAlgoName(lines, lang) {
  const code = lines.join('\n').toLowerCase();
  if (/bubble/.test(code))               return 'Bubble Sort';
  if (/selection.*sort/.test(code))      return 'Selection Sort';
  if (/insertion.*sort/.test(code))      return 'Insertion Sort';
  if (/merge.*sort/.test(code))          return 'Merge Sort';
  if (/quick.*sort|partition/.test(code))return 'Quick Sort';
  if (/heap.*sort/.test(code))           return 'Heap Sort';
  if (/\bsort\b/.test(code))             return 'Sorting Algorithm';
  if (/binary.*search/.test(code))       return 'Binary Search';
  if (/linear.*search/.test(code))       return 'Linear Search';
  if (/\bsearch\b/.test(code))           return 'Search Algorithm';
  if (/two.*pointer/.test(code))         return 'Two Pointer';
  if (/sliding.*window/.test(code))      return 'Sliding Window';
  if (/largest|maximum|max_val/.test(code))  return 'Find Maximum';
  if (/smallest|minimum|min_val/.test(code)) return 'Find Minimum';
  if (/fibonacci|fib/.test(code))        return 'Fibonacci';
  if (/twosum/.test(code))               return 'Two Sum';
  if (/palindrome/.test(code))           return 'Palindrome Check';
  if (/\bdfs\b/.test(code))             return 'Depth-First Search';
  if (/\bbfs\b/.test(code))             return 'Breadth-First Search';
  if (/knapsack/.test(code))             return 'Knapsack';
  if (/\bdp\b|dynamic/.test(code))      return 'Dynamic Programming';
  return 'Code Execution';
}

const LANG_COLORS = {
  python:'#3776ab', javascript:'#b8860b', c:'#4399c5', cpp:'#00796b',
};

// ── Init ──────────────────────────────────────────────────────────────────────
loadSample();
