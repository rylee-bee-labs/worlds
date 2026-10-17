/// <reference types="vitest/config" />
import { defineConfig, searchForWorkspaceRoot } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from 'node:path';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
import { playwright } from '@vitest/browser-playwright';
const dirname = import.meta.dirname;

// The Station serves UI and API same-origin in production; for dev and
// preview the API is proxied. Default target is the live backend; the
// e2e-fd-live suite overrides it (VITE_API_PROXY_TARGET) to the real
// dev API — see playwright.config.ts.
const API_TARGET = process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8000";

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig({
  // Deploy-time URL prefix (e.g. PW_VITE_BASE=/vnext/ for the vNext
  // station served behind a path prefix). Unset => served at root, so
  // dev, Playwright e2e and `vite preview` are unaffected.
  base: process.env.PW_VITE_BASE ?? "/",
  plugins: [react(), tailwindcss()],
  server: {
    // The Library's books live in ../docs/library and are bundled in.
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), path.resolve(dirname, "../docs/library")] },
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true
      },
      "/healthz": {
        target: API_TARGET,
        changeOrigin: true
      }
    }
  },
  test: {
    projects: [{
      extends: true,
      plugins: [
      // The plugin will run tests for the stories defined in your Storybook config
      // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
      storybookTest({
        configDir: path.join(dirname, '.storybook')
      })],
      test: {
        name: 'storybook',
        browser: {
          enabled: true,
          headless: true,
          provider: playwright({}),
          instances: [{
            browser: 'chromium'
          }]
        }
      }
    },
    {
      extends: true,
      test: {
        name: 'unit',
        environment: 'jsdom',
        // undici's Request (what jsdom tests get) cannot resolve a
        // relative baseUrl, so the typed client needs an absolute one
        // here. (The browser/storybook projects stay same-origin "".)
        env: { VITE_API_URL: 'http://station.test' },
        setupFiles: ['./src/test/setup.ts'],
        include: ['src/test/**/*.test.{ts,tsx}'],
      }
    }]
  }
});