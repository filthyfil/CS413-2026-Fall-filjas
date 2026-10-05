# AI Use Record – Assignment 4

**Tool:** Claude Code (Anthropic, model Claude Opus 5.5), used in the terminal.

## Important prompts

1. "i dont understand this line" (about the testing paragraph: a model test
   without a browser, a controller test with a substituted backend, and
   mocks not replacing real Lint and Interpret). The AI explained each
   sentence with small Python examples.
2. "Please familiarize yourself with the Assign04.md document. Do not begin
   working yet. Any questions?" The AI read the spec and `lambda1.py` and
   noted three things: only Python 3.10 was installed, while `lambda1.py`
   needs 3.12; `d0exp_fvset` was already supplied; and evaluation fails in
   several different ways (exceptions and the `D0V000()` sentinel). It then
   asked about the framework, timeouts, input limits, commits and samples.
3. "I believe the webapp should be written in vanilla js s.t. the compiler
   program can be embedded in the webapp as js." The AI pointed out that a
   JavaScript port of `lambda1.py` would conflict with "call
   `d0exp_evaluate` from `lambda1.py`", and suggested Pyodide as an
   alternative. It also wrongly read my message as "the compiler outputs
   JavaScript", which I corrected ("JS is not the target-language, nor did I
   say this?"). I then chose the simplest approach: a Python server with a
   plain JavaScript page.
4. "Ok, can you explain the point of Flask, I am unfamiliar." The AI
   explained what Flask does compared with `http.server`, and that Flask is
   only the HTTP plumbing, not the M, V or C.
5. "Be ware that I want to implement a canonical MVC model. Present a
   roadmap or plan for me to review." The AI proposed classic observer MVC in
   the browser (the View subscribes to the Model, and only the Controller
   changes it), with the Python server behind a backend interface. It also
   proposed a result contract, milestones and limits. I approved this.
6. "no limits; but let the user stop program compilation as they see fit.
   likely a worker thread for this?" The AI explained that Python threads
   cannot be killed, and proposed a child process per Interpret plus a Stop
   button and a `cancelled` status, with no timeout. It noted that F3 still
   requires a documented size limit, so we agreed on 1 MB.
7. "actually we may use node; and flask; etc". This settled the
   dependencies: Python 3.12 and Flask to run the app, plus Node 18 or later
   (built-in `node:test` only) for the JavaScript tests.
8. "do it" (install Node without sudo). The AI downloaded the official
   Node 22 build into `~/.local/node` and verified its checksum. The first
   JS test run showed that `node --test tests/js/` fails on Node 22, so
   the documented command became plain `node --test`.
9. "I think the results panel should have a clear." The AI added Clear
   results as a Model rule (`clearResults()`), a Controller method and a
   View button, with tests.
10. "Explain the implementation and architecture in terms of the MVC" and
   "V and C are bidirectional?" The AI explained each part's API and
   that the View-to-Controller link is one-way: the Controller never
   references the View and affects it only through the Model.
11. "Are we compliant with the spec; assignment?" The AI checked the
   submission against Assign04.md and listed what was still missing
   (browser test, my review, placeholders, push).
12. "ok, revise my reflection please, note any misconceptions". I wrote a
   first reflection; the AI expanded it to 280 words to cover all three
   required questions, and pointed out misconceptions (for example, that
   MVC by itself prevents spaghetti code, and that the Model is a full
   black box when the View reads its state fields directly).

## Significant suggestions from the AI

- Putting the MVC in the browser and keeping the server stateless, with the
  Controller (not the Model) calling the backend.
- A restricted `ast`-based constructor reader instead of `eval`, with a
  schema for each constructor and a check on operator names.
- The result contract (`ok`, `error`, `failure`, `not_implemented`,
  `cancelled`, plus an `errorKind`), and ignoring results that belong to an
  older revision.
- Running Interpret in a killable `spawn` child process with higher
  recursion and integer-printing limits, so `fact(5000)` works. Starting a
  new run stops an abandoned one.
- An artifact contract (`{revision, format, code}`) so a future Compile can
  enable Execute.
- The test plan, sample programs, and the TESTING.md mapping to F1–F10.

## Problems found while testing the AI's code

- The first smoke test failed because spawned child processes re-import the
  main script. This was a mistake in the AI's throwaway test script (it
  lacked an `if __name__ == "__main__"` guard), not in the app.
- Interpreting `fact(5000)` failed when printing the result, because of
  Python's 4300-digit limit for converting integers to strings. The AI
  raised that limit in the child process.
- Comment-only input and an unclosed parenthesis produced confusing "line 0"
  messages. The AI fixed the reader.
- The first version of the runner did not stop runs left over from an
  earlier request, even though the plan said it would. The AI added that
  and a test for it.

## How I reviewed the output

With 2k LOCs, reading the coding and fully understanding the system becomes unpractical; hence we should rely on good testing and verifying the operation by unit tests, manually using the website, and asking AI to perform code-review. I asked AI for the architectural report specifically about the MVC implementation, and the APIs between the different parts. I ensured that the implementation respects the classical MVC model covered in class. 
