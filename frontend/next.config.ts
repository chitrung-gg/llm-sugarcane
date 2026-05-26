import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  experimental: {
    // If your version of Next.js requires it under experimental
  },
  
  // Add the allowed origins for development (e.g., your local network IP)
  allowedDevOrigins: ["10.9.9.190", '100.88.18.97', '34.1.137.209'],

  // Bypasses CORS by proxying browser API requests through the Next.js server directly to the backend
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8008/api/v1/:path*',
      },
    ];
  },
};

export default nextConfig;