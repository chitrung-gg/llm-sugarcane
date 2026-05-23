import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    // If your version of Next.js requires it under experimental
  },
  // Add the allowed origins for development (e.g., your local network IP)
  allowedDevOrigins: ["10.9.9.190", '100.88.18.97'],
};

export default nextConfig;
