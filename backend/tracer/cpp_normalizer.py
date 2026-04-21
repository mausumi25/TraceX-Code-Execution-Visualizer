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
# Only used when class Solution is present.
_LEETCODE_STUBS: list[tuple[str, str]] = [
    (
        r"twoSum",
        """\
    vector<int> nums = {2, 7, 11, 15};
    int target = 9;
    Solution sol;
    auto ans = sol.twoSum(nums, target);
    cout << "[" << ans[0] << ", " << ans[1] << "]" << endl;""",
    ),
    (
        r"maxProfit|canJump|jump",
        """\
    vector<int> prices = {7, 1, 5, 3, 6, 4};
    Solution sol;
    auto ans = sol.maxProfit(prices);
    cout << ans << endl;""",
    ),
    (
        r"isPalindrome",
        """\
    Solution sol;
    cout << boolalpha << sol.isPalindrome("racecar") << endl;""",
    ),
    (
        r"isValid",
        """\
    Solution sol;
    cout << boolalpha << sol.isValid("()[]{}") << endl;""",
    ),
    (
        r"climbStairs|fib",
        """\
    Solution sol;
    cout << sol.climbStairs(5) << endl;""",
    ),
]

# Used when class Solution is found but no specific stub matched.
_SOLUTION_DEFAULT_STUB = """\
    Solution sol;
    // Auto-generated stub — add your own test call here
    cout << "Solution created." << endl;"""

# Used for plain C++ code (no class Solution, no main).
# Just prints the output of whatever the code does.
_PLAIN_MAIN_STUB = """\
    // Auto-generated main() — your code logic runs above via global scope or functions
    cout << "Program completed." << endl;"""


# ── Helpers ───────────────────────────────────────────────────────────────────
def _has_includes(code: str) -> bool:
    return bool(re.search(r"^\s*#include", code, re.MULTILINE))


def _has_main(code: str) -> bool:
    """Return True if the code already defines int main() (any signature)."""
    return bool(re.search(r"\bint\s+main\s*\(", code))


def _has_class_solution(code: str) -> bool:
    return bool(re.search(r"\bclass\s+Solution\b", code))


def _pick_leetcode_stub(code: str) -> str:
    """Return the most appropriate LeetCode main() body for the given code."""
    for pattern, stub in _LEETCODE_STUBS:
        if re.search(pattern, code):
            return stub
    return _SOLUTION_DEFAULT_STUB


def normalize(code: str) -> str:
    """
    Return a compilable version of *code*.

    Decision tree
    ─────────────
    1. Code already has both #include AND int main()   -> return as-is.
    2. Code has class Solution (LeetCode style):
       a. No #include  -> prepend standard headers
       b. No main()    -> append an appropriate Solution stub main()
    3. Plain C++ code (no class Solution, no main()):
       a. No #include  -> prepend standard headers
       b. No main()    -> append a minimal safe int main() {}
    """
    has_inc  = _has_includes(code)
    has_main = _has_main(code)

    # Case 1: Already complete — do nothing
    if has_inc and has_main:
        return code

    is_leetcode = _has_class_solution(code)

    # Prepend standard headers if missing
    if not has_inc:
        code = _STANDARD_HEADERS + "\n" + code.strip()

    # Append main() if still missing
    if not _has_main(code):
        if is_leetcode:
            stub = _pick_leetcode_stub(code)
        else:
            # Case 3: Plain C++ — just add a safe, minimal main()
            # that doesn't reference any class and won't cause linker errors.
            stub = _PLAIN_MAIN_STUB

        code = code.rstrip() + f"\n\nint main() {{\n{stub}\n    return 0;\n}}\n"

    return code
