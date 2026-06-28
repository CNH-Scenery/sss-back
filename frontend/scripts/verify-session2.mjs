import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const frontendDir = join(scriptDir, "..");

const requiredFiles = [
  "app/survey/page.tsx",
  "components/SurveyCard.tsx",
  "components/DecisionSelector.tsx",
  "components/ConfidenceSlider.tsx",
  "lib/api.ts",
  "lib/types.ts",
];

const missingFiles = requiredFiles.filter((file) => !existsSync(join(frontendDir, file)));
if (missingFiles.length > 0) {
  for (const file of missingFiles) {
    console.error(`Missing ${file}`);
  }
  process.exit(1);
}

const surveyPage = readFileSync(join(frontendDir, "app/survey/page.tsx"), "utf8");
const surveyCard = readFileSync(join(frontendDir, "components/SurveyCard.tsx"), "utf8");
const api = readFileSync(join(frontendDir, "lib/api.ts"), "utf8");

const checks = [
  ["scenarios endpoint", api.includes("/api/scenarios")],
  ["responses endpoint", api.includes("/api/responses")],
  ["SurveyCard usage", surveyPage.includes("SurveyCard")],
  ["can_generate_twin handling", surveyPage.includes("can_generate_twin")],
  ["decision input", surveyCard.includes("DecisionSelector")],
  ["confidence input", surveyCard.includes("ConfidenceSlider")],
  ["natural reason textarea", surveyCard.includes("textarea")],
];

const failed = checks.filter(([, passed]) => !passed);
if (failed.length > 0) {
  for (const [name] of failed) {
    console.error(`Missing ${name}`);
  }
  process.exit(1);
}

console.log("frontend session2 verification passed");
