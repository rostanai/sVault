import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // API base for the FastAPI backend (Vercel routes /api/* to the Python function).
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1",
  },
};

export default nextConfig;
