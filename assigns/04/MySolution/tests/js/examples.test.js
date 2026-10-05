// The canned examples must match the sample files used by the Python tests.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { EXAMPLES } from "../../web/js/examples.js";

for (const key of ["factorial", "fibonacci"]) {
  test(`${key} example matches samples/${key}.txt`, () => {
    const url = new URL(`../../samples/${key}.txt`, import.meta.url);
    assert.equal(EXAMPLES[key].text, readFileSync(url, "utf8"));
  });
}
