import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Note: Next.js 16 no longer runs ESLint during `next build`, so there's nothing
  // to disable here — lint is handled by CI as the quality gate.
  // API base for the FastAPI backend (Vercel routes /api/* to the Python function).
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1",
  },
};

export default nextConfig;
