import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  turbopack: {
    // The UI is an independent Next.js package inside the StateWake repository.
    // Pin Turbopack to this package so unrelated repository-level lockfiles do
    // not change module resolution or trigger workspace-root inference warnings.
    root: process.cwd(),
  },
};

export default nextConfig;
