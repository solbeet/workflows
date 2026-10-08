/**
 * Lint mínimo sin dependencias: falla si algún archivo de src/ o test/ tiene
 * espacios al final de línea o usa console.log. Reemplaza a ESLint en el
 * fixture para no sumar dependencias que mantener.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

/** @type {string[]} */
const errors = [];
for (const dir of ["src", "test"]) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    readFileSync(path, "utf8")
      .split("\n")
      .forEach((line, i) => {
        if (/\s+$/.test(line)) errors.push(`${path}:${i + 1}: espacios al final de línea`);
        if (line.includes("console.log")) errors.push(`${path}:${i + 1}: console.log`);
      });
  }
}
for (const error of errors) process.stderr.write(`${error}\n`);
process.exit(errors.length > 0 ? 1 : 0);
