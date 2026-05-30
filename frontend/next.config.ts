import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Don't fail the production build on ESLint findings — CI runs lint/typecheck
  // separately as the quality gate, so a stray lint warning never blocks a deploy.
  eslint: { ignoreDuringBuilds: true },
  // API base for the FastAPI backend (Vercel routes /api/* to the Python function).
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1",
  },
};

export default nextConfig;
