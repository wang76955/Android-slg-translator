import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "com.slgtranslator.app",
  appName: "SLG ????",
  webDir: "dist",
  server: {
    allowNavigation: ["api.openai.com", "api.deepseek.com"]
  },
  android: {
    allowMixedContent: true
  }
}

export default config
