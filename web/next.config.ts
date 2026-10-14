import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

if (process.env.DOCKER_BUILD === "1") {
  nextConfig.output = "standalone";
}

export default nextConfig;
