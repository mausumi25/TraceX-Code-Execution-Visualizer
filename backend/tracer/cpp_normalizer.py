"""
cpp_normalizer.py
─────────────────
Detects LeetCode-style C++ snippets (class Solution without #include / main)
and auto-prepends the standard-library headers they need, then wraps them in
a minimal main() that compiles and runs.

This lets users paste raw LeetCode solutions without manually adding boilerplate.
"""
import re

# ── Standard headers we always inject ────────────────────────────────────────
_STANDARD_HEADERS = """\
#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <map>
#include <set>
#include <queue>
#include <stack>
#include <deque>
#include <algorithm>
#include <numeric>
#include <cmath>
#include <climits>
#include <functional>
#include <sstream>
#include <utility>
using namespace std;
"""

# ── Minimal main() stubs for common LeetCode problem patterns ─────────────────
# Keyed by method-name pattern → (arg_setup, call_expr, print_expr)
_LEETCODE_STUBS: list[tuple[str, str]] = [
    # twoSum(vector<int>, int) -> vector<int>
    (
        r"twoSum",
        """\
    vector<int> nums = {2, 7, 11, 15};
    int target = 9;
    Solution sol;
    auto ans = sol.twoSum(nums, target);
    cout << "[" << ans[0] << ", " << ans[1] << "]" << endl;""",
    ),
    # maxProfit / canJump / jump — single vector<int>
    (
        r"maxProfit|canJump|jump",
        """\
    vector<int> prices = {7, 1, 5, 3, 6, 4};
    Solution sol;
    auto ans = sol.maxProfit(prices);
    cout << ans << endl;""",
    ),
    # isPalindrome(string)
    (
        r"isPalindrome",
        """\
    Solution sol;
    cout << boolalpha << sol.isPalindrome("racecar") << endl;""",
    ),
    # isValid(string) — valid parentheses
    (
        r"isValid",
        """\
    Solution sol;
    cout << boolalpha << sol.isValid("()[]{}") << endl;""",
    ),
    # climbStairs / fibonacci style int->int
    (
        r"climbStairs|fib",
        """\
    Solution sol;
    cout << sol.climbStairs(5) << endl;""",
    ),
]

_DEFAULT_STUB = """\
    Solution sol;
    // Auto-generated stub — add your own test call here
    cout << "Solution object created." << endl;"""


def _has_includes(code: str) -> bool:
    return bool(re.search(r"^\s*#include", code, re.MULTILINE))


def _has_main(code: str) -> bool:
    return bool(re.search(r"\bmain\s*\(", code))


def _has_class_solution(code: str) -> bool:
    return bool(re.search(r"\bclass\s+Solution\b", code))


def _pick_stub(code: str) -> str:
    """Return the most appropriate main() body for the given code."""
    for pattern, stub in _LEETCODE_STUBS:
        if re.search(pattern, code):
            return stub
    return _DEFAULT_STUB


def normalize(code: str) -> str:
    """
    Return a compilable version of *code*.

    Rules:
    1. If the code already has #include AND main() → return as-is.
    2. If it has #include but NO main() (class-only with headers) →
       append a main() wrapper.
    3. If it has NO #include (bare LeetCode snippet) →
       prepend standard headers and append a main() wrapper.
    """
    has_inc  = _has_includes(code)
    has_main = _has_main(code)

    # Already complete
    if has_inc and has_main:
        return code

    stub = _pick_stub(code)

    if not has_inc:
        # Prepend all standard headers
        code = _STANDARD_HEADERS + "\n" + code.strip()

    if not _has_main(code):
        # Append a minimal main()
        code = code.rstrip() + f"\n\nint main() {{\n{stub}\n    return 0;\n}}\n"

    return code
