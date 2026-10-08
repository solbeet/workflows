import assert from "node:assert/strict";
import { test } from "node:test";

import { formatCents } from "../src/format.js";

test("formatea centavos con dos decimales", () => {
  assert.equal(formatCents(1250), "12.50");
  assert.equal(formatCents(5), "0.05");
});

test("respeta el signo negativo", () => {
  assert.equal(formatCents(-199), "-1.99");
});

test("rechaza valores no enteros", () => {
  assert.throws(() => formatCents(1.5), TypeError);
});
