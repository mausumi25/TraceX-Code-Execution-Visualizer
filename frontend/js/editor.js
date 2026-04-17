/**
 * editor.js  —  CodeMirror 5 setup
 * Handles editor initialisation, language switching, and theme (dark/light).
 */
'use strict';

// ── Sample code per language ──────────────────────────────────────────────
const SAMPLES = {
  python: `# Two Sum — Python (LeetCode #1)
# Given an array of integers nums and an integer target,
# return indices of the two numbers that add up to target.

def two_sum(nums, target):
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

nums = [2, 7, 11, 15]
target = 9
result = two_sum(nums, target)
print("Input: nums =", nums, ", target =", target)
print("Output:", result)
`,

  javascript: `// Two Sum — JavaScript (LeetCode #1)
// Return indices of the two numbers that sum to target.

/**
 * @param {number[]} nums
 * @param {number} target
 * @return {number[]}
 */
function twoSum(nums, target) {
    const map = new Map();
    for (let i = 0; i < nums.length; i++) {
        const complement = target - nums[i];
        if (map.has(complement)) {
            return [map.get(complement), i];
        }
        map.set(nums[i], i);
    }
    return [];
}

const nums = [2, 7, 11, 15];
const target = 9;
console.log("Input: nums =", JSON.stringify(nums), ", target =", target);
console.log("Output:", JSON.stringify(twoSum(nums, target)));
`,

  c: `#include <stdio.h>
#include <stdlib.h>

/* Two Sum — C (LeetCode #1)
   Returns indices of the two numbers that add up to target. */

int* twoSum(int* nums, int numsSize, int target, int* returnSize) {
    *returnSize = 2;
    int* result = (int*)malloc(2 * sizeof(int));

    for (int i = 0; i < numsSize; i++) {
        for (int j = i + 1; j < numsSize; j++) {
            if (nums[i] + nums[j] == target) {
                result[0] = i;
                result[1] = j;
                return result;
            }
        }
    }
    result[0] = -1;
    result[1] = -1;
    return result;
}

int main() {
    int nums[] = {2, 7, 11, 15};
    int target = 9;
    int size = 4, retSize;

    int* ans = twoSum(nums, size, target, &retSize);
    printf("Output: [%d, %d]\\n", ans[0], ans[1]);
    free(ans);
    return 0;
}
`,

  cpp: `// LeetCode #1 — Two Sum (C++)
// Paste any LeetCode solution — headers & main() are added automatically!

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        int l = nums.size();
        for (int i = 0; i < l; i++) {
            for (int j = i + 1; j < l; j++) {
                if (nums[j] == target - nums[i])
                    return {i, j};
            }
        }
        return {-1, -1};
    }
};
`,
};

// ── CodeMirror modes ──────────────────────────────────────────────────────
const CM_MODES = {
  python:     { name: 'python' },
  javascript: { name: 'javascript' },
  c:          { name: 'clike', mime: 'text/x-csrc' },
  cpp:        { name: 'clike', mime: 'text/x-c++src' },
};

// ── Initialise editor ─────────────────────────────────────────────────────
let editor;

function initEditor() {
  const textarea = document.getElementById('code-editor');
  const isDark   = !document.documentElement.classList.contains('light-mode');

  editor = CodeMirror.fromTextArea(textarea, {
    mode:              CM_MODES.cpp,          // default to C++ (LeetCode feel)
    theme:             isDark ? 'one-dark' : 'default',
    lineNumbers:       true,
    matchBrackets:     true,
    autoCloseBrackets: true,
    tabSize:           4,
    indentWithTabs:    false,
    lineWrapping:      false,
    autoRefresh:       true,
    extraKeys: {
      Tab: cm => cm.execCommand('indentMore'),
    },
  });

  editor.setSize('100%', '100%');

  // Load default C++ Two Sum sample (matches the LeetCode example)
  editor.setValue(SAMPLES.cpp);

  // Set language selector to cpp
  const sel = document.getElementById('lang-select');
  if (sel) sel.value = 'cpp';

  editor.clearHistory();
  return editor;
}

// ── Language switch ───────────────────────────────────────────────────────
function switchLanguage(lang) {
  const modeConfig = CM_MODES[lang];
  if (!modeConfig || !editor) return;

  if (modeConfig.mime) {
    editor.setOption('mode', modeConfig.mime);
  } else {
    editor.setOption('mode', modeConfig.name);
  }
}

// ── Theme switch (called from main.js when toggle clicked) ────────────────
function setEditorTheme(isDark) {
  if (!editor) return;
  editor.setOption('theme', isDark ? 'one-dark' : 'default');
  editor.refresh();
}

// ── Helpers ───────────────────────────────────────────────────────────────
function getCode()        { return editor ? editor.getValue() : ''; }
function clearEditor()    { if (editor) { editor.setValue(''); editor.clearHistory(); } }
function loadSample(lang) { if (editor && SAMPLES[lang]) editor.setValue(SAMPLES[lang]); editor && editor.clearHistory(); }
function highlightLine(n) { if (editor) editor.setCursor({ line: n - 1, ch: 0 }); }

// Expose on window so main.js can use them
window.TraceEditor = { initEditor, switchLanguage, setEditorTheme, getCode, clearEditor, loadSample, highlightLine };
