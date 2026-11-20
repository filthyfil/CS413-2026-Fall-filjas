import { test } from "node:test";
import assert from "node:assert/strict";

import { attackPath, conflicts, describe } from "../../client/events.js";

test("conflicts finds column and both diagonal attackers", () => {
  assert.deepEqual(conflicts([0], 1, 0), [{ row: 0, column: 0, line: "column" }]);
  assert.deepEqual(conflicts([0], 1, 1), [{ row: 0, column: 0, line: "diagonal" }]);
  assert.deepEqual(conflicts([2], 1, 1), [{ row: 0, column: 2, line: "diagonal" }]);
  assert.deepEqual(conflicts([0, 4, 7], 3, 5), []);
  assert.equal(conflicts([1, 3, 0], 3, 3).length, 1);
});

test("attackPath lists the squares strictly between", () => {
  assert.deepEqual(attackPath({ row: 0, column: 0 }, { row: 3, column: 3 }),
    [{ row: 1, column: 1 }, { row: 2, column: 2 }]);
  assert.deepEqual(attackPath({ row: 0, column: 4 }, { row: 2, column: 4 }), [{ row: 1, column: 4 }]);
  assert.deepEqual(attackPath({ row: 1, column: 2 }, { row: 2, column: 1 }), []);
});

test("describe explains every event kind", () => {
  assert.equal(describe({ event: "try", column: 3, row: 1, board: [0] }, 8), "Row 1: trying column 3");
  assert.match(describe({ event: "place", column: 2, row: 1, board: [0, 2] }, 8), /safe, queen placed/);
  assert.equal(describe({ event: "reject", column: 1, row: 1, board: [0] }, 8),
    "Row 1: column 1 rejected, on the diagonal of queen at (row 0, col 0)");
  assert.match(describe({ event: "backtrack", column: 2, row: 1, board: [0] }, 4), /resume at column 3/);
  assert.match(describe({ event: "backtrack", column: 3, row: 1, board: [0] }, 4), /row 1 exhausted/);
  assert.equal(describe({ event: "solution", board: [1, 3, 0, 2] }, 4), "Solution found: [1, 3, 0, 2]");
  assert.match(describe({ event: "done" }, 4), /complete/);
});
