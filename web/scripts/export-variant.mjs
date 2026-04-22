import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const targetArg = process.argv[2];

if (!targetArg) {
  throw new Error("target directory is required");
}

const sourceDir = resolve("out");
const targetDir = resolve(targetArg);

if (!existsSync(sourceDir)) {
  throw new Error(`build output not found: ${sourceDir}`);
}

rmSync(targetDir, { recursive: true, force: true });
mkdirSync(targetDir, { recursive: true });
cpSync(sourceDir, targetDir, { recursive: true });

if (targetDir.endsWith("web_dist_studio")) {
  for (const blockedDir of ["accounts", "settings", "login", "image"]) {
    rmSync(resolve(targetDir, blockedDir), { recursive: true, force: true });
  }
}
