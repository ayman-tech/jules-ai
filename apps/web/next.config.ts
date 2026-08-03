import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  logging: {
    incomingRequests: {
      // Invitation paths contain one-time bearer secrets. Do not echo them to
      // development terminals; the API logs a redacted [token] placeholder.
      ignore: [/^\/invite\//],
    },
  },
};

export default nextConfig;
