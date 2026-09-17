import type { NextConfig } from "next";

const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Emits .next/standalone with only the files the server actually needs,
  // so the runtime image carries no dev dependencies and no full
  // node_modules. Required by services/frontend/Dockerfile; harmless for
  // `next dev`, which ignores it.
  output: "standalone",
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "womenshealth.gov",
        pathname: "/sites/default/files/**",
      },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
