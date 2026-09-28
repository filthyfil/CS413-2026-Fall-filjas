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
