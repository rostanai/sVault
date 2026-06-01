import path from "path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Tree-shake large barrel packages so only the icons/primitives actually used
  // are bundled — cuts the lucide-react barrel (~229KB) and Radix down massively,
  // which is the biggest contributor to slow First Contentful Paint.
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@radix-ui/react-dropdown-menu",
      "@radix-ui/react-dialog",
      "@radix-ui/react-select",
    ],
  },
  // Fix workspace root detection for Turbopack (avoids lockfile warning)
  turbopack: {
    root: path.resolve(__dirname),
  },
  env: {
    NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1",
  },
};

export default nextConfig;
