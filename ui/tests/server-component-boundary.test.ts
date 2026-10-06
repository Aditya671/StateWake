import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

function tsxFiles(root: string): string[] {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return tsxFiles(path);
    return entry.isFile() && entry.name.endsWith(".tsx") ? [path] : [];
  });
}

describe("Next.js App Router / Ant Design client boundary", () => {
  it("does not dot into Typography subcomponents from server-rendered app pages", () => {
    const appRoot = join(process.cwd(), "app");
    const violations = tsxFiles(appRoot).flatMap((path) => {
      const source = readFileSync(path, "utf8");
      const isClientModule = /^\s*["']use client["'];/.test(source);
      return !isClientModule && /\bTypography\.(?:Title|Paragraph|Text|Link)\b/.test(source)
        ? [path]
        : [];
    });

    expect(violations).toEqual([]);
  });
});
