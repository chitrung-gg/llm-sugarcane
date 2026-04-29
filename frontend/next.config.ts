import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    // If your version of Next.js requires it under experimental
  },
  // Add the allowed origins for development (e.g., your local network IP)
  allowedDevOrigins: ["192.168.198.100"],
};

export default nextConfig;
