# Requirements Specification: A Web-Based Environment for Testing LAMBDA (Version 1)

Status: **Draft for stakeholder review.** No stakeholder answers have been received yet.
Questions Q1–Q6 have been resolved from the brief (§4); Q7 and Q8 remain open.
Every other point the brief leaves open is recorded as an explicit assumption (A-*) or an
unresolved issue (U-*) and is **not** presented as a stakeholder decision.

Source document: *Stakeholder Brief: A Web-Based Environment for Testing LAMBDA*
(`../LAMBDA-UI-informal-requirements.md`), cited below as **[B: section]**.

---

## 1. Purpose

The software specified here, referred to simply as **the application**, is a browser-based
tool that, in Version 1, runs locally. With it, a user can write or load a LAMBDA program, send it to the LAMBDA
compiler to check or run it, understand the outcome, and keep programs as named, repeatable
tests. It replaces working "directly with the language tools" with a more convenient way
to try examples and check that the compiler has not regressed [B: intro].

**Terminology.** The brief uses "environment" for the whole system a user relies on when trying a
program. This specification keeps that meaning. **Environment** means the combined system:
the application, the compiler interface, the compiler, and the browser and computer they run
on. **The application** means only the software specified here. The user's **program** is the one
thing that is *not* part of the environment. That distinction drives the attribution rule
in §3.1.

### 1.1 Definitions

| Term | Meaning in this document |
| --- | --- |
| **Application** | The browser-based software specified in this document (not a product name). |
| **Environment** | The combined system the user depends on: the application, compiler interface, compiler (real or mock), local browser and computer. Excludes the user's program. |
| **Environment problem** | Any failure of a part of the environment, as opposed to a problem the compiler reports in the user's program (see §3.1 and FR-08). |
| **Compiler** | The LAMBDA language tools (parser, compiler and evaluator). Developed as a separate project, outside the application. |
| **Compiler interface** | The documented boundary through which the application sends source text and receives results (see §7). |
| **Check** | Ask the compiler to compile a program **without** running it. |
| **Run** | Ask the compiler to compile **and** run a program and return its value. |
| **Outcome** | The classified result of a Check or Run (see FR-08). |
| **Example** | A named program shipped with the application (e.g., factorial). |
| **Test** | A named program whose correct outcome is known, plus an **expectation** recording that outcome (expected value or expected rejection). A mismatch therefore points at the compiler, not the program (A-11). |
| **Collection** | A named, ordered set of tests. |
| **Mock mode** | Operation using sample compiler responses instead of the real compiler. |
| **Compiler artifacts** | Extra information the compiler may produce, e.g., an AST or generated code. |

## 2. Stakeholders and Goals

| Stakeholder | Main goals | Source |
| --- | --- | --- |
| **Instructor** (customer; lecture user) | Demonstrate examples live and switch between them quickly. Show compiler artifacts for teaching. Keep prepared examples across sessions. Agree on a small, useful v1 early. | [B: intro, Trying a program, Keeping the project manageable] |
| **Student – program writer** | Write, load and save LAMBDA programs. Run them and understand errors. Get started with no prior compiler experience. | [B: intro, Understanding what happened] |
| **Student – compiler developer** | Keep a collection of tests and re-run it after changing the compiler to detect regressions. | [B: intro, Keeping examples as tests] |
| **Developer** (builds both the application and the compiler) | Define and evolve the compiler interface as a stable, documented contract between the two. Build the application against mock responses before the compiler is ready, then connect the real compiler without rewriting the UI. | [B: The compiler is still evolving] |

## 3. Scope

### 3.1 System boundary

The application covers the **browser user interface**, **local persistence** of the user's
programs and tests, **test execution and comparison logic**, and an **adapter** that talks to
the compiler through the compiler interface. The **compiler itself is out of scope**
("Developing the compiler itself is a separate project" [B: The compiler is still evolving]).
The application never decides whether a program is valid LAMBDA. It reports what the
compiler says.

```
 ┌── Environment: the combined system (everything except the user's program) ───┐
 │  Browser + local computer                                                    │
 │  ┌────────────────────── Application (in scope) ───────────────────────┐     │
 │  │ Editor & examples │ Outcome display │ Tests & collections │ Storage │     │
 │  │                  └─────── Compiler adapter ───────┘                 │     │
 │  └──────────────────────────────┬──────────────────────────────────────┘     │
 │                                 │ compiler interface (§7, EI-1)              │
 │                 ┌───────────────┴───────────────┐                            │
 │                 │ Real LAMBDA compiler          │  Mock responses (EI-2)     │
 │                 │ (separate project)            │  (in scope, for demos)     │
 │                 └───────────────────────────────┘                            │
 └──────────────────────────────────────────────────────────────────────────────┘
        ▲ The user's LAMBDA program is the input to this system, not part of it.
```

**Attribution rule.** The application may report a problem as a fault *in the user's program*
(**Compile error** or **Runtime error**) only when the compiler has returned a well-formed
diagnostic about that program. Every other failure is an **Environment problem** and is
reported as one. This includes: the compiler cannot be reached; it crashes or fails
internally; its response is missing, malformed or in an unexpected format; the adapter
fails; the application itself has a fault; or local storage cannot be read or written. When
the cause is uncertain, the application shall treat it as an Environment problem and not blame
the program. This implements "If it cannot reach the compiler, I do not want students to
think their program is wrong" [B: Understanding what happened], applied to the whole
environment and not only to reaching the compiler.

*In a collection run*, a test's program is already known to have the recorded outcome (A-11).
A compiler internal failure or unexpected response on that program is still shown with the
**Environment problem** outcome (FR-08). However, the test counts as **failed** (FR-17),
because it indicates a compiler regression. This does not blame the program.

### 3.2 In scope for Version 1

Editing, built-in examples, loading and saving files, Check and Run, classified outcomes with
error locations, stopping long runs, optional viewing of compiler artifacts, named tests and
collections with a summary, persistence across reloads and sessions, mock mode, and local
installation.

### 3.3 Out of scope for Version 1

| Excluded | Reason |
| --- | --- |
| Public hosting, user accounts, authentication | Explicitly not requested [B: Keeping the project manageable] |
| Several people editing the same program together | Explicitly not requested [ibid.] |
| Developing or modifying the compiler | Separate project [B: The compiler is still evolving] |
| Full IDE features (debugger, refactoring, auto-completion) and sophisticated visual effects | Lower priority than reliable editing, understandable results and repeatable tests [B: Keeping the project manageable] |
| Server-based sharing of collections with the class | "Could live without that in the first version." A file-based workaround is offered as FR-19 (Could). |

## 4. Clarification Questions

No question has been answered by the instructor yet. On review, the brief was found to already
imply an answer to Q1–Q6. The *Answer* column records that resolution and marks it
**Resolved (from brief)**. It is a reading of the brief, not a stakeholder answer,
and the instructor may still overrule it. Q7 and Q8 are not settled by the brief and remain open;
the *Working position* column states how this draft proceeds in the meantime.

| ID | Question for the instructor | Why the answer matters | Answer | Working position |
| --- | --- | --- | --- | --- |
| Q1 | What form will the compiler interface take (command-line program, Python function, local service)? Which fields will a response include: value, error message, source location, AST, generated code? | Defines EI-1. Determines whether FR-09 (error locations) and FR-14 (artifacts) are possible and what they can display. | **Resolved (from brief):** the application is a local web app, so the compiler is invoked on the same computer through the EI-1 contract [B: Keeping the project manageable; The compiler is still evolving]. The application and the compiler are built by the same developer, so the interface is defined within this project. Responses carry the fields listed in EI-1, including source locations for errors. | A-1, A-2, A-10 |
| Q2 | "Change its input" for factorial: does a LAMBDA program read input separately, or is the input a value written in the source? | Decides whether the application needs a separate input field, and whether tests must store inputs. | **Resolved (from brief):** input is written in the source; programs are closed terms. No separate input field. | A-3 |
| Q3 | What kinds of values can a program produce (integers, Booleans, others such as functions or pairs)? How should an actual value be compared with an expected one? | Test pass/fail (FR-15, FR-16) depends on a precise comparison rule. | **Resolved (from brief):** the set of value kinds grows as the language specification grows. Comparison by exact equality of the compiler's printed form is kept. | A-4 |
| Q4 | For tests that expect rejection, is "the compiler rejected it" enough, or must the error kind, message or location also match? Should tests be able to expect a *runtime* error? | Changes the expectation types in FR-15 and how strict a regression check is. | **Resolved (from brief):** the brief names two expectations only, an answer or a rejection [B: Keeping examples as tests]. Rejection at compile time is enough, with an optional message substring. Expected runtime errors are not in v1. | A-5 |
| Q5 | Is it acceptable for work to be kept in the browser on that computer, or must it be kept as ordinary files on disk? | "Come back in another session" [B] can be met either way, but the two differ in backup, moving between browsers, and the risk of data loss. | **Resolved (from brief):** as a local web app, work is stored as files on the local disk, not in browser storage. | A-6 |
| Q6 | Should long-running programs be stopped automatically after a time limit? If so, what default? | Stopping by hand is required [B]. Also decides how a non-terminating test is handled in a collection run (FR-12). | **Resolved (from brief):** no. A program is never stopped automatically; only the user stops it [B: Understanding what happened]. | A-7 |
| Q7 | Which browsers and operating systems do students "normally use"? What may the setup instructions assume is already installed (e.g., Python)? | Makes QR-05 testable. Affects how the compiler is launched locally. | *Not yet received* | A-8 |
| Q8 | While the source notation is still being discussed, should saved examples and tests record which notation or compiler version they were written for? | If the syntax changes, stored examples may become invalid. Affects FR-02, FR-15 and EI-1 versioning. | *Not yet received* | U-2 |

## 5. Assumptions

| ID | Assumption (to be confirmed) | Affects |
| --- | --- | --- |
| A-1 | The compiler can be invoked on the user's computer with source text, and it returns a structured response that separates a successful value, a compile-time error and a runtime error. | FR-06–FR-08, EI-1 |
| A-2 | The compiler is expected to supply source locations for compile and runtime errors (Q1). Locations and compiler artifacts are still treated as **optional** fields, so the application behaves correctly (FR-09, FR-14) until the compiler provides them. | FR-09, FR-14 |
| A-3 | Program input is written in the source text. v1 has no separate input field. Programs are closed terms, as in the closed lambda calculus (no free variables), so a program never depends on outside input and the compiler can check it on its own. | FR-02, FR-15 |
| A-4 | Expected values are compared by exact equality of the compiler's printed form of the value (Q3). Integers and Booleans are the value kinds known now; further kinds are covered by the same rule as the language specification grows. | FR-15, FR-16 |
| A-5 | An "expected compile error" test passes if the compiler rejects the program at compile time. An optional expected-message substring may make it stricter. | FR-15 |
| A-6 | Work is stored as files on the local disk by the locally running application (Q5), so it survives reloads, browser restarts and a change of browser on the same computer. File export/import (FR-05, FR-19) provides portability to other computers. | FR-18, QR-04, EI-4 |
| A-7 | No automatic time limit is imposed. A Check or Run continues until it finishes or the user stops it (FR-11). *Rationale:* the brief says "some examples may run for a long time", and a short timeout would cut off legitimate long runs (Q6). | FR-11, FR-12 |
| A-8 | *Proposal:* supported browsers are the current stable releases of Chrome, Firefox and Edge on Windows, macOS and Linux. | QR-05 |
| A-9 | One user per installation. Work stored by an installation belongs to whoever uses that installation. | Scope |
| A-10 | The compiler's response distinguishes a diagnostic about the user's program from an internal failure of the compiler itself (EI-1). When it does not, for instance while the compiler is still evolving (for example, the compiler process terminates unexpectedly with no well-formed diagnostic), the application treats the case as an Environment problem. | FR-08, FR-10, EI-1 |
| A-11 | *Position:* a collection holds programs whose correct outcome is known: programs known to be good, with their expected values, and programs known to be rejected. A collection is not used to explore programs of unknown correctness; that is done with Check and Run. So in a collection run, a result that differs from the expectation, including a compiler internal failure or unexpected response, is treated as a compiler regression. | FR-15, FR-17, §3.1 |

## 6. Requirements

**Priority** uses MoSCoW: **M** = Must (v1 is not acceptable without it), **S** = Should
(expected in v1 and deferred only by agreement), **C** = Could (only if time permits).
*Rationale:* the brief ranks "reliable editing, understandable results, and repeatable tests"
above other features [B: Keeping the project manageable], so those capabilities are **M**.
Conveniences and anything the brief calls optional are **S** or **C**.

### 6.1 Functional requirements

**Editing and examples**

| ID | Requirement | Pri. |
| --- | --- | --- |
| FR-01 | The application shall provide a text editing area in which the user can type, paste and edit LAMBDA source text. Line numbers shall be shown. | M |
| FR-02 | The application shall provide a list of named built-in examples, including at least a factorial example. Selecting one shall load its source into the editor. | M |
| FR-03 | Editing a loaded example shall not change the built-in original. The user shall be able to restore an example's original text at any time. | M |
| FR-04 | The user shall be able to load a program from a text file on the local computer into the editor. | M |
| FR-05 | The user shall be able to save the program in the editor to a text file on the local computer. | M |

**Checking and running**

| ID | Requirement | Pri. |
| --- | --- | --- |
| FR-06 | The application shall provide a **Check** action. It sends the editor contents to the compiler for compilation only and reports the outcome **without** running the program. | M |
| FR-07 | The application shall provide a **Run** action. It sends the editor contents to the compiler to compile and run, and on success displays the value produced. | M |
| FR-08 | Every Check or Run shall end in exactly one outcome, displayed with a distinct text label: **Success**, **Compile error**, **Runtime error**, **Stopped** (by the user) or **Environment problem** (any failure of the environment, per the attribution rule in §3.1). **Compile error** and **Runtime error** shall be used only when the compiler has returned a well-formed diagnostic about the user's program. Messages for compile and runtime errors shall include the compiler's explanation text. | M |
| FR-09 | When the compiler's error response includes a source location, the application shall display the line (and column, if given) and provide an action that moves the editor cursor to that location and highlights it. | M |
| FR-10 | On an **Environment problem** outcome, the message shall state that the program was **not** evaluated and that the failure is not a fault in the program. It shall not show compile-error or runtime-error styling or source-location highlights. Where known, it shall name the part of the environment that failed (compiler unreachable, compiler internal failure, unexpected response, application fault, storage). The editor contents shall be left unchanged, and the user shall be able to retry the same action without re-entering the program. | M |
| FR-11 | While a Check or Run is in progress, the application shall show that work is in progress and offer a **Stop** action. After Stop, the outcome shall be **Stopped**, and the user shall be able to start a new action immediately. | M |
| FR-12 | The application shall not stop a Check or Run automatically (A-7). During a collection run, the user shall be able to stop the test currently running. That test shall be recorded as **Stopped**, and the run shall continue with the next test. The user shall also be able to stop the whole collection run, and tests not yet run shall be reported as not evaluated. | M |
| FR-13 | Each displayed outcome shall show which version of the source produced it. If the editor contents have changed since that action started, the outcome shall be marked **out of date** until a new action is performed. Only the result of the most recently started action shall be displayed as current. | M |
| FR-14 | When the compiler supplies artifacts (e.g., AST, generated code), the user shall be able to show them on request. Artifacts shall be hidden by default. When an artifact is not available, the application shall say so instead of showing an empty area. | S |

**Tests and collections**

| ID | Requirement | Pri. |
| --- | --- | --- |
| FR-15 | The user shall be able to create, rename, edit and delete **tests**. Each test has a name that is unique within its collection, a program, and one expectation: (a) *expected value* (A-4), or (b) *expected compile error*, optionally with a message substring (A-5). The user shall be able to create a test from the current editor contents. | M |
| FR-16 | The user shall be able to run all tests in a collection with one action. Each test shall be run independently. A test that fails, is stopped, or meets an Environment problem shall be recorded for that test only, and the remaining tests shall still be run. | M |
| FR-17 | After a collection run, the application shall display a summary: the number of tests that **passed**, **failed** and could **not be evaluated**. A test **failed** when its outcome did not match the expectation, or when the compiler failed internally or returned an unexpected response (A-11). A test is **not evaluated** when it was Stopped, or when a part of the environment other than the compiler failed (compiler unreachable, application fault, storage). For each failed or not-evaluated test it shall show the cause (mismatch, compiler internal failure, unexpected response, stopped by the user, or which other part of the environment failed, per FR-10), so that a compiler crash is distinguishable from a wrong value. For each failed or not-evaluated test it shall show the expected outcome, the actual outcome with compiler messages, and an action that opens the test's program in the editor. | M |

**Persistence and sharing**

| ID | Requirement | Pri. |
| --- | --- | --- |
| FR-18 | The editor contents, modified examples, tests and collections shall be saved automatically, with no explicit save action, as files on the local disk (A-6, EI-4). They shall be restored after a page reload, after the browser is closed and reopened, or when the application is opened in another browser on the same computer. If saving fails, the application shall tell the user that their work could not be saved, report it as an Environment problem and not a fault in the program, keep the editor contents, and retry saving. | M |
| FR-19 | The user shall be able to export a collection to a single file and import such a file, so that collections can be backed up or given to others (a partial answer to sharing). | C |

**Compiler integration**

| ID | Requirement | Pri. |
| --- | --- | --- |
| FR-20 | The application shall be able to operate in **mock mode** using sample compiler responses (EI-2). While mock mode is active, a persistent indicator shall be visible, and every outcome shall carry the label "SAMPLE RESPONSE – not produced by the compiler". The screen shall show whether the application is connected to the real compiler or to mock responses. | M |

### 6.2 Quality requirements

Numeric targets below are **proposals** made in this specification. The brief does not supply them.

| ID | Requirement | How satisfaction is assessed | Pri. |
| --- | --- | --- | --- |
| QR-01 **Keyboard operation** | Every M-priority user action (FR-01–FR-13, FR-15–FR-18, FR-20) shall be possible using only the keyboard, with a visible focus indicator. Selecting an example and Run shall have keyboard shortcuts. | A tester completes AC-02 and AC-07 without a mouse. | M |
| QR-02 **Not colour-only** | Every outcome and test status shall be conveyed by text or a symbol in addition to any colour. | Screenshots converted to greyscale are reviewed. Every status is still distinguishable. | M |
| QR-03 **Responsiveness** | *Proposal:* actions that do not involve the compiler (typing, selecting an example, switching views) show a visible response within 0.2 s on the reference computer. While a Check or Run is in progress, the editor stays editable and Stop stays usable. | Timed on a reference computer (to be agreed) while an infinite-loop program is running. | M |
| QR-04 **No data loss** | *Proposal:* after a page reload, browser crash or Environment problem, no more than the last 2 seconds of edits are lost, and no saved test or collection is lost. | Edit, wait 2 s, force-close the browser, reopen, compare. | M |
| QR-05 **Getting started** | *Proposal:* a person who has used neither the application nor the compiler can, on a supported platform (A-8), install and start the application by following only the written setup instructions, then load an example, run it and read its result using only on-screen text, in 20 minutes or less in total, with no more than 2 of those minutes spent after the application is running. | Observed trial with 3 students not involved in the project. Setup time and first-use time are recorded separately. | S |

## 7. External Interfaces and Dependencies

| ID | Interface | Description |
| --- | --- | --- |
| EI-1 | **Compiler interface** (boundary between the application and the compiler) | The application shall reach the compiler only through a single documented, versioned contract, defined within this project. **Requests:** operation (Check or Run) and source text. **Responses:** outcome kind (success, compile error, runtime error, or internal compiler failure, kept distinct from diagnostics about the program; where the compiler does not yet report this, A-10 applies), value (on success), message text, source location for errors (optional until the compiler supplies it, A-2), optional artifacts, and optional compiler version. Replacing mock responses with the real compiler, or one compiler version with another that honours the contract, shall require no change to the user interface [B: The compiler is still evolving]. The application runs locally and invokes the compiler on the same computer (Q1); the exact request and response format is documented as part of this contract. |
| EI-2 | **Mock response provider** | Supplies sample responses in the EI-1 format for demonstrations and development. It shall cover every outcome kind in FR-08, so that the UI can be tested before the compiler exists. |
| EI-3 | **Local file system** | Used through the browser's standard open and save dialogs for FR-04, FR-05 and FR-19. Program files are plain text. |
| EI-4 | **Local data files** | Files on the local disk, written and read by the locally running application, that hold the persisted data for FR-18 (A-6). |
| EI-5 | **Web browser** | The only user-facing interface. Supported browsers per A-8. |

**Dependency risk:** the compiler and its source notation are still changing (U-2). Until the compiler
implements EI-1, FR-09 and FR-14 can be verified only in mock mode.

## 8. Unresolved Issues

| ID | Issue | Needed from |
| --- | --- | --- |
| U-2 | How stored examples and tests behave when the source notation changes (Q8). | Instructor |
| U-4 | Whether sharing beyond file export is wanted in a later version. | Instructor |

## 9. Acceptance Criteria

These are specifications of future checks. No system has been tested.

| ID | Req. | Starting conditions | Action / input | Expected observable result |
| --- | --- | --- | --- | --- |
| AC-01 | FR-02, FR-03 | Application open, real or mock compiler. | Select *factorial*, change the argument in its source, then choose "restore original". | The edited text is replaced by the unchanged built-in factorial source. Selecting factorial again in a new session also shows the original. |
| AC-02 | FR-07, FR-08 | Compiler available. Factorial example loaded with argument 5. | Run. | Outcome labelled **Success** with the value `120`. No compiler artifacts are shown. |
| AC-03 *(failure)* | FR-08, FR-09 | Compiler available and supplies locations. Editor contains a program with a syntax error on line 3. | Check. | Outcome labelled **Compile error** with the compiler's message and "line 3". Activating the location moves the cursor to line 3 and highlights it. The program is not run. |
| AC-04 *(failure)* | FR-08, FR-10, QR-04 | The compiler process is stopped or unreachable. The editor holds an unsaved, valid program. | Run. Then restart the compiler and choose Retry. | First result is labelled **Environment problem** and states the program was not evaluated, not that it contains an error. The editor text is unchanged. Retry yields **Success**. |
| AC-05 *(exceptional)* | FR-11, QR-03 | Editor contains a recursive program that never terminates. | Run, type in the editor for 5 s, then press Stop. | An in-progress indicator is shown while typing stays responsive. After Stop, the outcome is **Stopped** and a new Run can start immediately. |
| AC-06 | FR-13 | A Run of program version A is in progress. | Edit the program (version B) before the result arrives. | When A's result arrives, it is shown marked **out of date** and identified as belonging to version A. It is not shown as the result for B. |
| AC-07 *(failure)* | FR-12, FR-16, FR-17 | Collection of 4 tests in order: correct, wrong expected value, non-terminating, correct. | Run the collection. When the third test has been running for 10 s, stop that test. | All 4 tests are reported, and the fourth test still runs. Summary: 2 passed, 1 failed, 1 not evaluated (cause: stopped by the user). The failed test shows expected and actual values, and "open in editor" loads its program. |
| AC-08 | FR-18 | User has edited the program and created a collection with 2 tests. | Wait 2 s, then reload the page. Then close and reopen the browser. | After each step, the editor contents and both tests are present unchanged. |
| AC-09 | FR-20 | Application started in mock mode. | Run any example. | A mock-mode indicator is visible throughout. The outcome carries the "SAMPLE RESPONSE" label. |
| AC-10 | QR-02 | Collection results from AC-07 displayed. | Convert a screenshot to greyscale. | Passed, failed and not-evaluated tests are still distinguishable by text or symbol. |
| AC-11 *(failure)* | FR-08, FR-10 | A compiler build (or mock response) that crashes, or returns a malformed response, for a valid program. | Run the valid program. | Outcome labelled **Environment problem** identifying a compiler internal failure or unexpected response. **Not** labelled Compile error or Runtime error. No source line is highlighted. The editor text is unchanged. |
| AC-12 *(failure)* | FR-17, A-11 | Collection of 3 tests with correct expectations. The compiler (or a mock response) crashes on the second test. | Run the collection. | Summary: 2 passed, 1 failed, 0 not evaluated. The failed test's cause is shown as a compiler internal failure, not as a wrong value. The third test still runs. |

## 10. Traceability

| Req. | Brief section / passage | Answer or assumption |
| --- | --- | --- |
| FR-01 | Trying a program ("typing or pasting a short program") | — |
| FR-02 | Trying a program ("a few examples… factorial example") | A-3 |
| FR-03 | Trying a program ("modify an example without losing access to the original") | — |
| FR-04 | Trying a program ("programs saved in files… not have to retype") | — |
| FR-05 | Trying a program ("keep a program… return to it later") | A-6 |
| FR-06 | Trying a program ("only want to check whether a program compiles") | A-1 |
| FR-07 | Trying a program ("run it and see the answer") | A-1 |
| FR-08 | Understanding what happened ("compilation error and a failure while running… should not look like the same thing"; "cannot reach the compiler") | A-1, A-10 |
| FR-09 | Understanding what happened ("help the student find that place in the source") | A-2 |
| FR-10 | Understanding what happened ("The environment itself may have problems too… not… think their program is wrong… keep their work and try again") | A-10 |
| FR-11 | Understanding what happened ("a way to stop it and move on"; "remain usable") | — |
| FR-12 | Understanding what happened ("might never finish… a way to stop it and move on"); Keeping examples as tests ("one troublesome test") | A-7, Q6 |
| FR-13 | Understanding what happened ("know which version produced the result") | — |
| FR-14 | Trying a program ("inspect… abstract syntax tree or generated code… not… get in the way") | A-2 |
| FR-15 | Keeping examples as tests ("named tests… expect an answer… expect the compiler to reject") | A-4, A-5, Q3, Q4 |
| FR-16 | Keeping examples as tests ("run the collection again"; "one troublesome test should not make the rest… useless") | — |
| FR-17 | Keeping examples as tests ("quick summary… enough detail to investigate"; "check whether anything has broken") | A-11 |
| FR-18 | Keeping examples as tests ("refreshing the page… losing the examples"; "another session"); Understanding what happened ("keep their work") | A-6, Q5 |
| FR-19 | Keeping examples as tests ("sharing… could live without that") | U-4 |
| FR-20 | The compiler is still evolving ("sample compiler responses… nobody mistakes them") | — |
| QR-01 | Keeping the project manageable ("main tasks with a keyboard"; "move between examples") | — |
| QR-02 | Keeping the project manageable ("without depending only on colors") | — |
| QR-03 | Keeping the project manageable ("respond promptly… even when the compiler takes longer") | Proposed target |
| QR-04 | Understanding what happened ("keep their work"); Keeping examples as tests ("refreshing") | Proposed target |
| QR-05 | Intro ("easy to get started… not used the compiler before"); Keeping the project manageable ("browser students normally use"; "another person can follow the instructions") | A-8, Q7, proposed target |
| EI-1, EI-2 | The compiler is still evolving ("connect the real compiler without starting the interface over") | A-1, A-2, A-10, Q1 |
| EI-3 | Trying a program ("programs saved in files"; "keep a program") | Supports FR-04, FR-05, FR-19 |
| EI-4 | Keeping examples as tests ("refreshing the page"; "another session") | A-6, Q5; supports FR-18 |
| EI-5 | Keeping the project manageable ("a browser students normally use") | A-8 |

## 11. Review Notes

Issues found while reviewing an earlier draft, and how each was resolved:

1. **Unverifiable requirement: "detect programs that never terminate."** In general this
   cannot be decided. It was replaced by a user **Stop** action (FR-11), and in collection
   runs by stopping a single test and moving on to the next (FR-12). Both have observable
   results. An automatic short timeout was considered and rejected (A-7), because legitimate
   programs may run for a long time.
2. **Contradiction between autosave and preserving originals.** Automatic saving (FR-18) could
   have overwritten built-in examples. FR-03 now requires edits to be kept apart from the
   originals, and AC-01 checks that an original survives a new session.
3. **Vague wording: "respond promptly" and "easy to get started."** These were turned into
   QR-03 and QR-05, with measurable targets explicitly marked as proposals, and the
   compiler's own run time was separated from the UI's response time.
4. **Ambiguous test failure.** "One troublesome test" did not say whether a hung test counts
   as *failed*. A third status, *not evaluated*, was added (FR-17), so that environment problems
   and stopped tests are not mistaken for compiler regressions.
5. **Missing behaviour: results from an earlier run.** The first draft said nothing about a
   late response arriving after an edit. FR-13 and AC-06 now cover it.
6. **Unsupported requirement: a separate program-input field.** "Change its input" [B] first
   suggested an input field. The brief does not say that LAMBDA programs read input, so the
   field was dropped. The point became assumption A-3 and question Q2, instead of a
   requirement based on a guess.
7. **Terminology and a gap in attribution.** The draft used "the Environment" as the name of
   the software. As a result, "Environment problem" covered only one case: the compiler
   could not be reached. In the brief, "environment" means the whole system, so a compiler
   crash, a malformed response or an application fault could still have been shown as a
   fault in the student's program. The software is now called only "the application" and
   has no product name. "Environment" was defined as the combined system, and an attribution
   rule was added (§3.1). It lets only well-formed compiler diagnostics blame the program.
   FR-08, FR-10, A-10, EI-1 and AC-11 implement it.
8. **A compiler crash in a collection run was counted as "not evaluated".** Under the
   attribution rule, a crash in a collection run was reported as not evaluated, so a student
   who broke the compiler could miss the regression. Collections hold programs whose outcome
   is already known (A-11), so a crash there cannot be a fault in the program. It now counts
   as **failed**, with the cause shown (FR-17, AC-12). The outcome label is still
   Environment problem (§3.1), and U-5 was removed.
