import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = join(scriptDir, "..");
const pagePath = join(frontendDir, "app", "page.tsx");
const source = readFileSync(pagePath, "utf8");

const checks = [
  ["CoinTwin MVP title", source.includes("CoinTwin MVP")],
  ["backend health endpoint", source.includes("/health")],
  ["API base env", source.includes("NEXT_PUBLIC_API_BASE_URL")],
  ["offline state", source.includes("offline")],
];

const failed = checks.filter(([, passed]) => !passed);

if (failed.length > 0) {
  for (const [name] of failed) {
    console.error(`Missing ${name}`);
  }
  process.exit(1);
}

console.log("frontend session0 verification passed");
