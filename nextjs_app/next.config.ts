import type { NextConfig } from "next";

import { version } from "./package.json";

const nextConfig: NextConfig = {
  // PROJ-8: App-Version zur Build-Zeit injizieren (Sidebar-Badge) — nicht manuell
  // gepflegt, sondern aus package.json. Zentral gelesen über lib/version.ts.
  env: {
    NEXT_PUBLIC_APP_VERSION: version,
  },
};

export default nextConfig;
