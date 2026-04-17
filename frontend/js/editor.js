/**
 * editor.js  —  CodeMirror 5 setup
 * Handles editor initialisation and language switching.
 */
'use strict';

// ── Sample code per language ──────────────────────────────────────────────
const SAMPLES = {
  python: `# Fibonacci — step through and watch the call stack
def fibonacci(n):
    if n <= 1:
        return n
    a, b = 0, 1
    for i in range(2, n + 1):
        a, b = b, a + b
    return b

result = fibonacci(8)
print("fibonacci(8) =", result)
`,

  javascript: `// Bubble sort — watch variables change on every swap
function bubbleSort(arr) {
    const n = arr.length;
    for (let i = 0; i < n - 1; i++) {
        for (let j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                let temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
    return arr;
}

const data = [64, 34, 25, 12, 22, 11, 90];
const sorted = bubbleSort(data);
console.log("Sorted:", JSON.stringify(sorted));
`,

  c: `#include <stdio.h>

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

int main() {
    int num = 6;
    int result = factorial(num);
    printf("factorial(%d) = %d\\n", num, result);
    return 0;
}
`,

  cpp: `#include <iostream>
#include <vector>
#include <algorithm>

int main() {
    std::vector<int> nums = {5, 2, 8, 1, 9, 3};

    std::sort(nums.begin(), nums.end());

    std::cout << "Sorted: ";
    for (int n : nums) {
        std::cout << n << " ";
    }
    std::cout << std::endl;

    return 0;
}
`,
};

// ── CodeMirror modes ──────────────────────────────────────────────────────────
const CM_MODES = {
  python:     { name: 'python' },
  javascript: { name: 'javascript' },
  c:          { name: 'clike', mime: 'text/x-csrc' },
  cpp:        { name: 'clike', mime: 'text/x-c++src' },
};

// ── Initialise editor ─────────────────────────────────────────────────────────
let editor;

function initEditor() {
  const textarea = document.getElementById('code-editor');

  editor = CodeMirror.fromTextArea(textarea, {
    mode:              CM_MODES.python,
    theme:             'one-dark',
    lineNumbers:       true,
    matchBrackets:     true,
    autoCloseBrackets: true,
    tabSize:           4,
    indentWithTabs:    false,
    lineWrapping:      false,
    extraKeys: {
      Tab: cm => cm.execCommand('indentMore'),
    },
  });

  // Make editor fill the wrapper
  editor.setSize('100%', '100%');

  // Load default Python sample
  editor.setValue(SAMPLES.python);
  editor.clearHistory();

  return editor;
}

// ── Language switch ───────────────────────────────────────────────────────────
function switchLanguage(lang) {
  const modeConfig = CM_MODES[lang];
  if (!modeConfig) return;

  if (modeConfig.mime) {
    editor.setOption('mode', modeConfig.mime);
  } else {
    editor.setOption('mode', modeConfig.name);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function getCode()           { return editor ? editor.getValue() : ''; }
function clearEditor()       { if (editor) { editor.setValue(''); editor.clearHistory(); } }
function loadSample(lang)    { if (editor && SAMPLES[lang]) editor.setValue(SAMPLES[lang]); }
function highlightLine(n)    { if (editor) editor.setCursor({ line: n - 1, ch: 0 }); }

// Expose on window so main.js can use them
window.TraceEditor = { initEditor, switchLanguage, getCode, clearEditor, loadSample, highlightLine };
