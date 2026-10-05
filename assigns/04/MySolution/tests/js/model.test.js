// Model tests: plain Node, no browser, no server, no backend.
import test from "node:test";
import assert from "node:assert/strict";

import { AppModel, MAX_SOURCE_BYTES, sourceProblem } from "../../web/js/model.js";

const PROGRAM = 'D0Eop2("+", D0Eint(20), D0Eint(22))';
const result = (op, revision, status = "ok", extra = {}) =>
  ({ op, revision, status, message: "", errorKind: null, value: null, details: {}, ...extra });

function loaded(text = PROGRAM) {
  const m = new AppModel();
  m.loadSource("prog.txt", text);
  return m;
}

test("starts empty with every action blocked", () => {
  const m = new AppModel();
  assert.equal(m.applied, null);
  assert.equal(m.draft, null);
  for (const op of ["lint", "interpret", "typecheck", "compile", "execute"]) {
    assert.equal(m.canRun(op), false);
  }
});

test("subscribers are notified on change and can unsubscribe", () => {
  const m = new AppModel();
  let calls = 0;
  const off = m.subscribe(() => { calls += 1; });
  m.loadSource("a", PROGRAM);
  assert.equal(calls, 1);
  off();
  m.loadSource("b", PROGRAM);
  assert.equal(calls, 1);
});

test("manual input without upload: blank editor, type, apply", () => {
  const m = new AppModel();
  assert.ok(m.openManualInput().ok);
  assert.deepEqual([m.draft.name, m.draft.text], ["Manual input", ""]);
  assert.equal(m.canRun("lint"), false);
  m.editDraft(PROGRAM);
  assert.ok(m.hasUnappliedEdits);
  assert.ok(m.applyDraft().ok);
  assert.deepEqual(m.applied, { name: "Manual input", text: PROGRAM, revision: 1 });
  assert.ok(m.canRun("lint") && m.canRun("interpret"));
});

test("every accepted change makes a new revision and clears results", () => {
  const m = loaded();
  assert.equal(m.applied.revision, 1);
  m.beginOperation("lint", "r1");
  m.completeOperation(result("lint", 1));
  assert.equal(m.results.length, 1);

  m.editDraft(PROGRAM + " ");
  m.applyDraft();
  assert.equal(m.applied.revision, 2);
  assert.deepEqual(m.results, []);

  m.loadSource("other", 'D0Eint(1)');
  assert.equal(m.applied.revision, 3);
  assert.equal(m.applied.text, "D0Eint(1)");
});

test("rejects empty and whitespace-only source but keeps applied state", () => {
  const m = loaded();
  for (const bad of ["", "   \n\t "]) {
    const before = { ...m.applied };
    assert.equal(m.loadSource("bad", bad).ok, false);
    assert.deepEqual(m.applied, before);
    assert.equal(m.notice.kind, "error");
  }
});

test("rejected edits stay in the editor for correction", () => {
  const m = loaded();
  m.editDraft("   ");
  const r = m.applyDraft();
  assert.equal(r.ok, false);
  assert.match(r.reason, /empty/);
  assert.equal(m.applied.text, PROGRAM);       // previous applied source kept
  assert.equal(m.applied.revision, 1);
  assert.equal(m.draft.text, "   ");            // rejected edit kept
  assert.ok(m.hasUnappliedEdits);
  m.editDraft('D0Eint(5)');
  assert.ok(m.applyDraft().ok);
  assert.equal(m.applied.revision, 2);
});

test("size limit is counted in UTF-8 bytes", () => {
  assert.equal(sourceProblem("x".repeat(MAX_SOURCE_BYTES)), null);
  assert.match(sourceProblem("x".repeat(MAX_SOURCE_BYTES + 1)), /limit/);
  assert.match(sourceProblem("é".repeat(MAX_SOURCE_BYTES / 2 + 1)), /limit/);
  const m = loaded();
  assert.equal(m.loadSource("big", "#".repeat(MAX_SOURCE_BYTES + 1)).ok, false);
  assert.equal(m.applied.text, PROGRAM);
});

test("unapplied edits block tools and source replacement", () => {
  const m = loaded();
  m.editDraft(PROGRAM + "\n# changed");
  assert.equal(m.canRun("lint"), false);
  assert.match(m.blockedReason("interpret"), /Apply or discard/);
  assert.equal(m.canReplaceSource, false);
  assert.equal(m.loadSource("other", "D0Eint(1)").ok, false);
  assert.equal(m.openManualInput().ok, false);
  assert.equal(m.applied.revision, 1);
});

test("discard restores the applied source", () => {
  const m = loaded();
  m.editDraft("D0Eint(9)");
  assert.ok(m.discardDraft().ok);
  assert.equal(m.draft.text, PROGRAM);
  assert.equal(m.hasUnappliedEdits, false);
  assert.ok(m.canRun("lint"));
  // also after opening a new manual program on top of an applied one
  m.openManualInput();
  assert.equal(m.canRun("lint"), false);
  m.discardDraft();
  assert.ok(m.inSync);
});

test("applied edits do not change the original source name", () => {
  const m = loaded();
  m.editDraft("D0Eint(3)");
  m.applyDraft();
  assert.equal(m.applied.name, "prog.txt");
});

test("busy state blocks every action, edits and replacement", () => {
  const m = loaded();
  assert.ok(m.beginOperation("interpret", "run-1").ok);
  assert.deepEqual(m.busy, { op: "interpret", runId: "run-1", revision: 1, stopping: false });
  assert.equal(m.canRun("lint"), false);
  assert.equal(m.editDraft("D0Eint(2)").ok, false);
  assert.equal(m.loadSource("x", "D0Eint(1)").ok, false);
  assert.equal(m.canApply, false);
  assert.equal(m.beginOperation("lint", "run-2").ok, false);
  assert.ok(m.completeOperation(result("interpret", 1)).ok);
  assert.equal(m.busy, null);
  assert.ok(m.canRun("lint"));
});

test("failures and cancellations offer retry; success clears it", () => {
  const m = loaded();
  m.beginOperation("interpret", "a");
  m.markStopping();
  assert.equal(m.busy.stopping, true);
  m.completeOperation(result("interpret", 1, "cancelled"));
  assert.equal(m.retryOp, "interpret");
  m.beginOperation("interpret", "b");
  assert.equal(m.retryOp, null);
  m.completeOperation(result("interpret", 1, "failure"));
  assert.equal(m.retryOp, "interpret");
  assert.equal(m.applied.text, PROGRAM);       // source preserved after failure
});

test("stale results (wrong op or revision) are ignored", () => {
  const m = loaded();
  m.beginOperation("lint", "a");
  assert.equal(m.completeOperation(result("lint", 0)).ok, false);
  assert.equal(m.completeOperation(result("interpret", 1)).ok, false);
  assert.ok(m.busy);
  assert.ok(m.completeOperation(result("lint", 1)).ok);
  assert.equal(m.completeOperation(result("lint", 1)).ok, false); // not busy
  assert.equal(m.results.length, 1);
});

test("execute stays unavailable without a generated artifact", () => {
  const m = loaded();
  assert.equal(m.canRun("execute"), false);
  assert.match(m.blockedReason("execute"), /no generated artifact/);
  m.beginOperation("compile", "c");
  m.completeOperation(result("compile", 1, "not_implemented"));
  assert.equal(m.artifact, null);
  assert.equal(m.canRun("execute"), false);
});

test("a future compile artifact enables execute until the source changes", () => {
  const m = loaded();
  m.beginOperation("compile", "c");
  m.completeOperation(result("compile", 1, "ok",
    { details: { artifact: { revision: 1, format: "future", code: "" } } }));
  assert.ok(m.canRun("execute"));
  m.editDraft("D0Eint(2)");
  m.applyDraft();
  assert.equal(m.artifact, null);
  assert.equal(m.canRun("execute"), false);
});
