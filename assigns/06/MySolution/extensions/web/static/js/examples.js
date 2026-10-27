// Canned examples for the Load source menu. kind is the result kind
// suggested for Execute when the example is loaded.

export const EXAMPLES = {
  factorial: {
    name: "Factorial",
    kind: "nat",
    text: "# fact 4 (expected: 24). Compile, then Execute with result kind nat.\n((fix fact(n). (if (n == 0) then 1 else (n * (fact (n - 1))))) 4)\n",
  },
  fibonacci: {
    name: "Fibonacci",
    kind: "nat",
    text: "# fib 5 with fib(0)=0, fib(1)=1 (expected: 5). Result kind: nat.\n((fix fib(n). (if (n < 2) then n else ((fib (n - 1)) + (fib (n - 2))))) 5)\n",
  },
  shortcircuit: {
    name: "Short-circuit",
    kind: "bool",
    text: "# false and LOOP (expected: false). The right operand is never run.\n# Result kind: bool.\n(false and ((fix loop(x). (loop x)) 0))\n",
  },
  pair: {
    name: "Nested pair",
    kind: "((nat, bool), nat)",
    text: "# pair (pair 2 true) 3 (expected: ((2, true), 3)).\n# Result kind: ((nat, bool), nat).\n(pair (pair 2 true) 3)\n",
  },
  loop: {
    name: "LOOP",
    kind: "nat",
    text: "# LOOP = (fix loop(x). loop x) 0 (expected: step-budget exhaustion).\n((fix loop(x). (loop x)) 0)\n",
  },
};
