import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = join(scriptDir, "..");

const requiredFiles = ["app/twin/page.tsx", "lib/api.ts", "lib/types.ts"];
const missingFiles = requiredFiles.filter((file) => !existsSync(join(frontendDir, file)));
if (missingFiles.length > 0) {
  for (const file of missingFiles) {
    console.error(`Missing ${file}`);
  }
  process.exit(1);
}

const twinPage = readFileSync(join(frontendDir, "app/twin/page.tsx"), "utf8");
const api = readFileSync(join(frontendDir, "lib/api.ts"), "utf8");
const types = readFileSync(join(frontendDir, "lib/types.ts"), "utf8");

const checks = [
  ["latest endpoint", api.includes("/api/twin-contexts/latest")],
  ["generate endpoint", api.includes("/api/twin-contexts/generate")],
  ["TwinContext type", types.includes("TwinContext")],
  ["style summary display", twinPage.includes("style_summary")],
  ["important signals display", twinPage.includes("important_signals")],
  ["avoid conditions display", twinPage.includes("avoid_conditions")],
  ["uncertainty display", twinPage.includes("uncertainty")],
  ["generate button", twinPage.includes("generateTwinContext")],
];

const failed = checks.filter(([, passed]) => !passed);
if (failed.length > 0) {
  for (const [name] of failed) {
    console.error(`Missing ${name}`);
  }
  process.exit(1);
}

console.log("frontend session3 verification passed");
