// Canned examples for the Load source menu (same text as samples/*.txt;
// tests/js/examples.test.js checks that they stay identical).

export const EXAMPLES = {
  factorial: {
    name: "Factorial (canned)",
    text: "# Factorial of 10 (expected: D0Vint(arg1=3628800)).\n# fact is a recursive function (fix) with parameter n.\nD0Eapp(\n  D0Efix(\"fact\", \"n\",\n    D0Eif0(\n      D0Eop2(\"<=\", D0Evar(\"n\"), D0Eint(0)),\n      D0Eint(1),\n      D0Eop2(\"*\",\n        D0Evar(\"n\"),\n        D0Eapp(D0Evar(\"fact\"), D0Eop2(\"-\", D0Evar(\"n\"), D0Eint(1)))))),\n  D0Eint(10))\n",
  },
  fibonacci: {
    name: "Fibonacci (canned)",
    text: "# Fibonacci number 15 (expected: D0Vint(arg1=610)).\n# fib is a recursive function (fix) with parameter n.\nD0Eapp(\n  D0Efix(\"fib\", \"n\",\n    D0Eif0(\n      D0Eop2(\"<\", D0Evar(\"n\"), D0Eint(2)),\n      D0Evar(\"n\"),\n      D0Eop2(\"+\",\n        D0Eapp(D0Evar(\"fib\"), D0Eop2(\"-\", D0Evar(\"n\"), D0Eint(1))),\n        D0Eapp(D0Evar(\"fib\"), D0Eop2(\"-\", D0Evar(\"n\"), D0Eint(2)))))),\n  D0Eint(15))\n",
  },
};
