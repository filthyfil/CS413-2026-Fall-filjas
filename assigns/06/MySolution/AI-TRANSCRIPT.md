# AI Use Record – Midterm 1 (Assignment 6)

**Tool:** Claude Code (Anthropic, model Claude Opus 5.5), used in the terminal
in a single long session. The AI read the assignment and my earlier
solutions, wrote code and documents into `MySolution/`, and ran the tests and
the demo. I directed the work step by step and asked questions along the
way.

## Important prompts and suggestions

1. **"look at assign 06 and distill the details to me".** The AI read
   `Assign06.md`, `REQUIREMENTS.md` and my notes, and summarized the four
   tasks, the required demonstrations, the testing obligations, the
   deliverables and the grading weights. It pointed out that my notes
   mentioned type checking, which the spec explicitly does not require.
2. **"what is input example to the compiler".** The AI explained that the
   input is a source AST built from the `D0E*` constructors, not text, and
   wrote out several demonstrations as constructor expressions.
3. **"i believe that the previous assignments cover a bit of the spec".** The
   AI agreed only in part. It listed what carried over from Assignment 5
   (fresh names, the substitution algorithm, the printer, alpha-equivalence)
   and Assignment 4 (the web UI). It also pointed out that the supplied
   `EvaluateVisitor` could not serve as the source evaluator: its
   subtraction is not truncated, it accepts `/`, it has no `not`, `and` or
   `or`, and the spec forbids delegating to a separate source evaluator.
4. **"copy the reusable parts into 06 and start the target AST".** The AI
   copied my A05 visitors with attribution and wrote `target.py` (frozen
   `Var`/`Lam`/`App`, printer, free variables, substitution, De Bruijn
   alpha-equivalence) with tests.
5. **"copy it dont import".** At first
   the AI imported the supplied file from `../05`, and it explained the
   tradeoff: one source of truth versus a self-contained folder. I chose to
   copy. The AI made a byte-identical copy and added `test_source_copy.py`,
   which fails if the copy ever changes.
6. **"ok great. now the reducer", then "why not use a stack?" and "what is a
   beta step".** The AI wrote the bounded call-by-value reducer as a loop
   and used an explicit stack. It explained that a recursive version uses one
   Python frame per beta step and crashes at about 1,000 steps, well before
   the budgets the spec needs. A test runs 100,000 steps of Ω to check this.
7. **"ok now create the inverse program for the pretty printer".** The AI
   wrote a recursive-descent parser for the printer's notation. It noted two
   ambiguities that come from the printer itself: keywords cannot be
   variable names, and `(-1 e)` could be either a unary operator or an
   application.
8. **"exactly now extend the reducer for ast".** The AI extended the same
   machine to run source ASTs, so one evaluator handles both languages, as
   the spec requires. One of its own tests was wrong: it expected a type
   error before the right operand ran, but call-by-value evaluates both
   operands first. The AI fixed the test, not the evaluator.
9. **"ok now the church encoding library".** The AI wrote the encodings and
   the observers. Two problems came up. The module was first named
   `encodings.py`, which clashes with a Python standard-library module, so
   it was renamed `church.py`. The first boolean markers let `NUM(2)` decode
   as `false`, so the AI replaced them with three-binder markers that cannot
   land on each other by accident. It also recorded in a test that
   `lam x. x` decodes as `1` (the eta-reduced numeral one), since the spec
   does not require rejecting every invalid untyped term.
10. **"what is eta reducting" / "why … say no eta; what does rejecting eta do
    for the compiler".** The AI explained that alpha and beta define
    computation, while eta is an extensionality equation that is false for
    non-values under call-by-value. It explained that `Z` is `Y` with one eta
    expansion, so allowing eta would break recursion and delayed branches.
11. **"ok now the compiler".** The AI wrote `CompileVisitor` and the
    rejection checks, plus 38 tests: every constructor and operator, scope,
    name collisions, divergence, purity, FV preservation, and a test that
    swaps in an evaluator that fails if called. All passed on the first run.
12. **"ok now the demo runner, but … the website in assign04", and "remember
    though to have the seperation of gradede items vs extensions".** The AI
    wrote `pipeline.py` and `demo.py`, then copied my A04 web app into
    `extensions/web/` and connected Compile and Execute (result kind and both
    budgets) to the core. Following my instruction, it moved the parsers and
    the website into `extensions/` and added `test_modules.py`, which fails
    if the core ever imports an extension.
13. **"scope and purity checks".** The AI added `test_properties.py`: 500
    seeded random programs whose names collide with encoding and thunk
    names. To show that the suite can fail, it planted three scope bugs in
    the compiler (a non-fresh thunk parameter, swapped `fix` binders, and a
    wrongly scoped `let` initializer). All three were caught, and the
    unmodified compiler passed.
14. **"walk me through the stages of the typical source program".** The
    AI traced `let x = 3 in (lam y. x + y) 4` through every stage using real
    output: 4 execution steps, 13 observation steps, decoded value 7.
15. **"yeah so use the pipeline design pattern for the system".** The
    AI said the system is a pipeline, the compiler is a
    Visitor, the evaluator is an abstract machine, and only `num(n)` and
    Flask's `create_app` really count as factories. I changed how I describe
    the architecture.
16. **"why do we evaluate before compilation" / "what walkthrough slide".**
    The AI admitted that its walkthrough had put the source evaluation in the
    wrong order. The demo compiles and runs first, and evaluates the source
    afterwards, only as an independent reference. It also admitted that no
    slide existed yet: it had misspoken.
17. **"Please fix the type errors"**

## How the results were reviewed and tested

What the AI ran during the session:

- The core suite, 137 tests:
  `python3.12 -m unittest discover -s MySolution -p 'test_*.py'`.
- The extension suite, 19 tests: run with Flask installed; without Flask, 11
  of them are skipped.
- `python3.12 MySolution/demo.py`: all 14 required demonstrations and 6
  additional examples match their expected answers and the source
  evaluator.
- Checks that the tests can actually fail: the planted-bug runs above, and
  tests written to catch earlier mistakes (the marker collision and the
  operand-order test).
- The web server, started for real with Interpret run over HTTP. The other
  operations are covered by the Flask test-client suite.
- Static type checking with mypy 2.4.0 over the core, the extensions and all
  test files: no issues in 31 files (`mypy.ini` holds the configuration).

I asked the AI to create a parser so I can write programs easily and verify the output. I read and oversaw the coding process, while suggesting design patterns and software design practices explored in class.

The code was further validated over unit tests and system tests. The python code wastyped checked using mypy, which caught 48 errors in the core. I also suggested some approaches to the software like using a stack to maintain the recursion of the LAMBDA language.

I asked AI to explain some of the theory, some of which was unclear to me, the concept of the Z combinator, what eta redex is, and the beta steps, and I made sure the respective python code that implements it is what I expected.


