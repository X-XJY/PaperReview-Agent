import test from "node:test";
import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { packageSite, packageSource, command } from "./package.mjs";

function fixture() {
  const base = resolve("artifacts/packaging-tests");
  mkdirSync(base, { recursive: true });
  const root = mkdtempSync(resolve(base, "project with spaces "));
  mkdirSync(resolve(root, "dist/assets"), { recursive: true });
  mkdirSync(resolve(root, ".openai"));
  writeFileSync(
    resolve(root, "dist/index.html"),
    '<html lang="zh-CN">论文预览</html>',
  );
  writeFileSync(
    resolve(root, "dist/assets/app.js"),
    'console.log("evidence");',
  );
  writeFileSync(
    resolve(root, ".openai/hosting.json"),
    JSON.stringify({
      project_id: "test-project",
      static: { directory: "dist" },
    }),
  );
  writeFileSync(resolve(root, ".env"), "TEST_SECRET=must-not-be-packed");
  writeFileSync(
    resolve(root, "server.py"),
    "# Must not be in the static archive",
  );
  return root;
}

test("packages paths with spaces, excludes backend/secrets, verifies tar bytes, and repeats safely", () => {
  const root = fixture();
  const first = packageSite(root);
  assert.equal(first.file_count, 3);
  assert(first.files.includes(".openai/hosting.json"));
  assert(
    !first.files.some(
      (name) => name.includes(".env") || name.includes("server.py"),
    ),
  );
  assert.match(readFileSync(first.path).toString("hex").slice(0, 4), /^1f8b$/);
  const second = packageSite(root);
  assert.equal(second.file_count, 3);
  assert.equal(
    command("tar", ["-xOf", second.path, "dist/index.html"], root),
    '<html lang="zh-CN">论文预览</html>',
  );
});

test("refuses accidental secrets inside build output", () => {
  const root = fixture();
  writeFileSync(resolve(root, "dist/.env"), "SECRET");
  assert.throws(() => packageSite(root), /private files/);
});

test("refuses static output with runtime bindings", () => {
  const root = fixture();
  writeFileSync(
    resolve(root, ".openai/hosting.json"),
    JSON.stringify({
      project_id: "test",
      static: { directory: "dist" },
      r2: {},
    }),
  );
  assert.throws(() => packageSite(root), /runtime bindings/);
});

test("requires a successful build before packaging", () => {
  const root = mkdtempSync(resolve("artifacts/packaging-tests", "empty "));
  assert.throws(() => packageSite(root), /Missing dist/);
});

test("source archive records exact commit and rejects dirty source", () => {
  const root = fixture();
  writeFileSync(resolve(root, ".gitignore"), ".env\nartifacts/\ndist/\n");
  command("git", ["init", "-b", "main"], root);
  command("git", ["add", "."], root);
  command(
    "git",
    [
      "-c",
      "user.name=Packaging Test",
      "-c",
      "user.email=test@localhost",
      "commit",
      "-m",
      "fixture",
    ],
    root,
  );
  const output = packageSource(root);
  assert.equal(
    output.commit,
    command("git", ["rev-parse", "HEAD"], root).trim(),
  );
  assert.equal(readFileSync(output.path).subarray(0, 2).toString(), "PK");
  writeFileSync(resolve(root, "server.py"), "# Changed after commit");
  assert.throws(() => packageSource(root), /Commit source changes/);
});
