import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { dirname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "./build.mjs";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export function command(executable, args, cwd, binary = false) {
  const result = spawnSync(executable, args, {
    cwd,
    shell: false,
    encoding: binary ? undefined : "utf8",
    maxBuffer: 32 * 1024 * 1024,
  });
  if (result.error)
    throw new Error(`Cannot run ${executable}: ${result.error.message}`);
  if (result.status !== 0)
    throw new Error(`${executable} failed: ${String(result.stderr).trim()}`);
  return result.stdout;
}

function hash(data) {
  return createHash("sha256").update(data).digest("hex");
}

function inside(root, target) {
  const rel = relative(root, target);
  if (!rel || rel === ".." || rel.startsWith(`..${sep}`) || isAbsolute(rel)) {
    throw new Error("Output must stay in the project artifacts directory.");
  }
}

export function regularFiles(root, current = root) {
  if (
    !lstatSync(current).isDirectory() ||
    lstatSync(current).isSymbolicLink()
  ) {
    throw new Error("Build root must be a regular directory.");
  }
  const files = [];
  for (const entry of readdirSync(current, { withFileTypes: true })) {
    const path = resolve(current, entry.name);
    if (entry.isSymbolicLink() || (!entry.isDirectory() && !entry.isFile())) {
      throw new Error("Build contains a symlink or special file.");
    }
    if (entry.isDirectory()) files.push(...regularFiles(root, path));
    else files.push(relative(root, path).split(sep).join("/"));
  }
  return files.sort();
}

function artifactRoot(root) {
  const folder = resolve(root, "artifacts");
  inside(root, folder);
  if (
    existsSync(folder) &&
    (lstatSync(folder).isSymbolicLink() || !lstatSync(folder).isDirectory())
  ) {
    throw new Error("Artifacts directory must not be a symlink or file.");
  }
  mkdirSync(folder, { recursive: true });
  return folder;
}

export function packageSite(root = projectRoot) {
  root = resolve(root);
  const buildRoot = resolve(root, "dist");
  const hostingPath = resolve(root, ".openai/hosting.json");
  if (!existsSync(resolve(buildRoot, "index.html")))
    throw new Error("Missing dist/index.html. Run npm run build first.");
  if (!existsSync(hostingPath))
    throw new Error("Missing .openai/hosting.json for the registered site.");
  const hosting = JSON.parse(
    readFileSync(hostingPath, "utf8").replace(/^\uFEFF/, ""),
  );
  if (!hosting.project_id || hosting.static?.directory !== "dist") {
    throw new Error(
      "This packager supports the registered static dist site only.",
    );
  }
  if (Object.keys(hosting).some((k) => !["project_id", "static"].includes(k))) {
    throw new Error(
      "Static archives cannot contain runtime bindings or secrets.",
    );
  }
  const files = regularFiles(buildRoot);
  if (
    files.some((name) =>
      /(^|\/)(\.env(?:\..*)?|\.git|node_modules|data)(\/|$)/.test(name),
    )
  ) {
    throw new Error("Build contains forbidden private files.");
  }
  const artifacts = artifactRoot(root);
  // A fresh staging directory avoids recursive deletion and locks on Windows.
  const stage = mkdtempSync(resolve(artifacts, "site-stage-"));
  const stagedBuild = resolve(stage, "dist");
  cpSync(buildRoot, stagedBuild, { recursive: true, dereference: false });
  mkdirSync(resolve(stagedBuild, ".openai"), { recursive: true });
  writeFileSync(
    resolve(stagedBuild, ".openai/hosting.json"),
    JSON.stringify(hosting) + "\n",
  );
  const stagedFiles = regularFiles(stagedBuild);
  const temporary = resolve(artifacts, `site-${Date.now()}.tar.gz`);
  command("tar", ["-C", stage, "-czf", temporary, "dist"], root);
  const entries = command("tar", ["-tzf", temporary], root)
    .trim()
    .split(/\r?\n/)
    .filter(Boolean);
  if (
    entries.some(
      (name) => !name.startsWith("dist/") || name.split("/").includes(".."),
    )
  ) {
    throw new Error("Archive contains a path outside dist.");
  }
  const archivedFiles = entries.filter((name) => !name.endsWith("/")).sort();
  if (
    JSON.stringify(archivedFiles) !==
    JSON.stringify(stagedFiles.map((name) => `dist/${name}`).sort())
  ) {
    throw new Error("Archive file list differs from validated build.");
  }
  // Verify the bytes inside the archive, not just successful tar exit status.
  for (const name of stagedFiles) {
    const archived = command(
      "tar",
      ["-xOf", temporary, `dist/${name}`],
      root,
      true,
    );
    if (hash(archived) !== hash(readFileSync(resolve(stagedBuild, name)))) {
      throw new Error(`Archive checksum mismatch: ${name}`);
    }
  }
  const output = resolve(artifacts, "site.tar.gz");
  renameSync(temporary, output);
  const manifest = {
    project_id: hosting.project_id,
    archive: "site.tar.gz",
    sha256: hash(readFileSync(output)),
    file_count: stagedFiles.length,
    files: stagedFiles,
  };
  writeFileSync(
    resolve(artifacts, "site-manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  return { path: output, ...manifest };
}

export function cleanCommit(root = projectRoot) {
  const status = command(
    "git",
    ["status", "--porcelain", "--untracked-files=normal"],
    root,
  ).trim();
  if (status)
    throw new Error(
      "Commit source changes before creating release archives, so source and build match.",
    );
  return command("git", ["rev-parse", "--verify", "HEAD"], root).trim();
}

export function packageSource(root = projectRoot) {
  const commit = cleanCommit(root);
  const files = command("git", ["ls-tree", "-r", "--name-only", "HEAD"], root)
    .trim()
    .split(/\r?\n/);
  if (
    files.some((name) =>
      /^(\.env$|\.env\.(?!example$)|data\/|node_modules\/|\.venv\/|artifacts\/)/.test(
        name,
      ),
    )
  ) {
    throw new Error(
      "Tracked source includes private or generated files. Remove them from Git before packaging.",
    );
  }
  const output = resolve(artifactRoot(root), "paper-method-agent-source.zip");
  command(
    "git",
    ["archive", "--format=zip", `--output=${output}`, "HEAD"],
    root,
  );
  const manifest = {
    commit,
    archive: "paper-method-agent-source.zip",
    sha256: hash(readFileSync(output)),
  };
  writeFileSync(
    resolve(root, "artifacts/source-manifest.json"),
    JSON.stringify(manifest, null, 2) + "\n",
  );
  return { path: output, ...manifest };
}

if (
  process.argv[1] &&
  resolve(process.argv[1]) === fileURLToPath(import.meta.url)
) {
  try {
    const mode = process.argv[2] || "all";
    if (!["all", "site", "source"].includes(mode))
      throw new Error(
        "Usage: node scripts/package.mjs [all|site|source] [--build]",
      );
    const commit = cleanCommit();
    if (process.argv.includes("--build")) build();
    const output = { commit };
    if (mode !== "source") output.site = packageSite();
    if (mode !== "site") output.source = packageSource();
    console.log(JSON.stringify(output, null, 2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
