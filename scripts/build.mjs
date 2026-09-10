import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function build(root = projectRoot) {
  // Launch JS entrypoints with the running Node executable. No nested npm.cmd,
  // Bash dependency, shell quoting, or assumption that paths contain no spaces.
  for (const [relative, args] of [
    ["node_modules/typescript/bin/tsc", ["-b"]],
    ["node_modules/vite/bin/vite.js", ["build"]],
  ]) {
    const entry = resolve(root, relative);
    if (!existsSync(entry))
      throw new Error("Dependencies missing. Run npm ci first.");
    const result = spawnSync(process.execPath, [entry, ...args], {
      cwd: root,
      stdio: "inherit",
      shell: false,
    });
    if (result.error) throw result.error;
    if (result.status !== 0)
      throw new Error(`${relative} failed (exit ${result.status}).`);
  }
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    build();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
