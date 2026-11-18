import { tmpdir } from "node:os";
import { join } from "node:path";

export const DB_PATH = join(tmpdir(), "undercover-e2e.db");
