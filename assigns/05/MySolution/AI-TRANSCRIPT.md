# AI Use Record – Assignment 5

**Tool:** Claude Code (Anthropic, model Claude Opus 5.5), used in the terminal.

## Important prompts

1. "can you explain the visitor design pattern? My understanding is some
   object flows through a pipeline and the pipeline adds its necessary
   information to the object, or does some processing, then advances the
   object elsewhere". The AI said that this describes a pipeline or chain of
   responsibility instead. In Visitor the structure stays fixed and the
   operation moves over it. It explained `accept` and double dispatch, and the
   trade-off: new operations are easy, new node types are hard.
2. "Ok, got it now whats capture avoiding substitution?" The AI explained free
   and bound variables, the two mistakes of naive replacement (replacing bound
   occurrences, and capture), and renaming a binder to a fresh name
   (alpha-equivalence) before substituting.
3. "explain de bruijn indices more". The AI explained nameless indices,
   shifting, substitution and beta reduction with indices, and De Bruijn
   levels.
4. "look at assignment 05 with me." The AI read `Assign05.md`, the supplied
   code and the tests. It pointed out that `MySolution/` was empty and the due
   date was today, and summarized the requirements. It flagged the hard
   cases, such as `fix f(f)`, and asked how I wanted to divide the work.
5. "Read the D0ExpVisitor and FreeVariableVisitor and EvaluateVisitor. I
   believe we need to implement the fix let pairs and projection nodes." The
   AI pointed out, with line numbers, that these nodes are already fully
   implemented in the supplied code. The requirement means that my new
   visitors must handle them.
6. "in MySolution implement the PrettyPrintVisitor; The class should evaluate
   which accept to choose given tree's type, and then the accept dispatches
   again to the printer class". The AI corrected one detail: the language
   picks `accept` from the node's class, and the visitor does not choose it.
   It then wrote `PrettyPrintVisitor` and `d0exp_pretty`. On the first run,
   the default `python3` turned out to be 3.10, which cannot import
   `lambda1_vp.py`, so all runs since then use Python 3.12.
7. "Yes, use 3.12. Then we need to implement the capture avoiding
   substitution ... I am wondering if this concept is similar to the SSA".
   The AI explained that SSA and renaming both give each binding a unique
   name. SSA renames everything in advance (comparable to the Barendregt
   convention), while substitution renames only when needed. It wrote
   `AllNamesVisitor`, `FreshNames` and `SubstitutionVisitor`, and ran them
   on all the examples from the spec.
8. "Does DeBruijns indices a variation of this". The AI answered that it is
   an alternative representation that removes the need for renaming. It
   suggested using a De Bruijn conversion as the optional alpha-equivalence
   checker in the tests.
9. "yes, add the alpha-equivalence checker and write both test suites, what
   strategy did you go with? the Barendergt convention?" The AI answered:
   lazy renaming, not Barendregt, because the spec asks to avoid unnecessary
   renaming. It wrote `DeBruijnVisitor`/`d0exp_alpha_equiv`,
   `shared_cases.py`, and the two suites. To check that the tests can fail,
   it ran them against two deliberately broken substitutions: "never rename"
   failed 25 subtests, and "`fix f(f)` renames only the parameter" failed 4.
10. "Ok, we are renaming, but what is the source of the new names?" The AI
    explained `FreshNames`: the used set is seeded from every name in the
    expression and the replacement plus the target, the generator tries
    `base_1`, `base_2`, ... in order, and one supply is shared by the whole
    call.
11. "yes install pytest and run the suite". `pip install --user` was refused
    (PEP 668, externally managed Python), so the AI created `assigns/05/.venv`
    with uv and installed pytest 9.1.1 there. Results: pytest 189 passed,
    unittest 22 passed. It deleted the `__pycache__/` that the run created.
12. "yes write the README and AI transcript, leave the human parts for me."
    The AI wrote this file and `README.md`, and left the design explanation
    and the review section below for me.

## What the AI wrote

| File | Written by |
| --- | --- |
| `lambda1_visitors.py` (all visitors and entry points) | AI |
| `shared_cases.py`, `test_unittest_suite.py`, `test_pytest_suite.py` | AI |
| `README.md`, excluding the Design section | AI |
| This file, except the section below | AI |

## Corrections to my understanding

- Visitor is not a pipeline: the operation travels over a fixed structure,
  and nothing is passed along to a next stage (prompt 1).
- `fix`, `let`, pairs and projections were already implemented in the
  supplied visitors. The work was to cover them in the new visitors
  (prompt 5).
- The visitor does not choose which `accept` runs; the language's method
  dispatch on the node does that (prompt 6).

## How I reviewed and tested the AI's output

I reviewed the code by reading it, and inquirying about the ideas of different substitution strategies. First before I started vibecoding, I just reviewed the core concepts that are needed to complete the assignment, like the visitor DP, and the theory for capture avoid substitution. Then I ask AI to implement the parts. After each part, I reviewed the code manually, so check for general logic and stylistic consistency. I ask for the tests to be generated in parallel, which I can review while the code trace is still close to my mind.

I changed the tests a little bit and intuited the behavior, which I verify by either test passing or failing.

I test the correct functionality for storing used names that will NOT be generated as a fresh name for alpha conversion.

Of course, in accordance with the conversation with AI, I ensured that the visitor design pattern is preserved, and noted the double dispatch idea.


