import { defineConfig } from "@playwright/test";
import { DB_PATH } from "./e2e/db";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: "http://localhost:5173" },
  webServer: [
    {
      command: "uv run -m uvicorn backend.main:app --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      env: { UNDERCOVER_DB: DB_PATH, UNDERCOVER_SCRIPTED_MODEL: "1" },
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5173 --strictPort",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
