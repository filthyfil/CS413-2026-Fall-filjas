# AI Use Record – Assignment 3

**Tool:** Claude Code (Anthropic, model Claude Opus 5.5), used in the terminal.

## Important prompts

1. "yes please draft the requirements doc using the principles of requirements engineering."
   Sent as a follow-up while the AI was working: "Make sure you have read the briefing, and
   understand the scope and constraints"
2. "trim to 5 quality requirements per spec." The AI merged the separate setup and first-use
   requirements into one end-to-end "Getting started" requirement (QR-05) instead of
   dropping one, because the spec warns against combining requirements just to hit a count.
3. "the environment is not the name of the software, but rather refers to the aggregate
   system … if the environment is wrong, it should not blame the user's program." I corrected
   the AI's terminology. It then defined "environment" as the combined system and added an
   attribution rule (§3.1): only well-formed compiler diagnostics may blame the program.
   It also broadened FR-08 and FR-10 and added A-10 and AC-11.
4. "I believe the questions in Clarification questions are deeply implied in the requirements
   doc with the stakeholder … a local webapp means that the files are stored on disk. a program
   should not be automatically stoped. i think 7 and 8 are valid". I resolved Q1–Q6 from the
   brief. The AI recorded these answers as team resolutions, not stakeholder answers, and
   switched storage from the browser to files on disk (A-6, FR-18, EI-4). It also removed
   U-1 and U-3. Q7 and Q8 stay open.
5. "the collection is programs that are known to be good." In reply, the AI pointed out that
   a compiler crash during a collection run then signals a regression rather than a fault in
   the program. On my approval it added A-11, redefined "Test", changed FR-17 so that such
   crashes count as failed, added AC-12, and removed U-5.

## Significant suggestions from the AI

- The overall structure of `REQUIREMENTS.md`: stakeholders, scope, questions, assumptions,
  requirements with MoSCoW priorities, interfaces, acceptance criteria, traceability, and
  review notes.
- Five outcome categories (FR-08), including a separate "Environment problem" category.
- A "not evaluated" status for test runs, and the "out of date" marking for results that
  arrive after the program has been edited.
- Proposed numeric targets (0.2 s UI response, 20 min setup plus first use). These are
  labelled as proposals, not stakeholder decisions. The AI also proposed a 10 s automatic
  time limit, which I rejected: long programs are stopped by the user instead (A-7, FR-12).

## How I reviewed the output

I read over the requirements carefully, revising unclear or overly verbose language in the specification. The AI was naming things that haven't been agreed upon in the spec, so I changed this. I changed some unnecessary proposals that the AI has created. I then asked AI to review my changes for logical error and gaps, and finished.
