import type { StorybookConfig } from '@storybook/react-vite';

const config: StorybookConfig = {
  // No **/*.mdx entry: autodocs come from the story files' `tags:
  // ["autodocs"]`. The mdx glob matched zero files and made every
  // storybook build/test run shout "No story files found".
  "stories": [
    "../src/**/*.stories.@(js|jsx|mjs|ts|tsx)"
  ],
  "addons": [
    "@chromatic-com/storybook",
    "@storybook/addon-vitest",
    "@storybook/addon-a11y",
    "@storybook/addon-docs",
    "@storybook/addon-mcp"
  ],
  "framework": "@storybook/react-vite",
  /**
   * The preview bundle co-locates every story with msw's browser
   * worker, react-aria and the storybook runtime — its largest chunk
   * is ~1.6 MB. That is fine for a documentation/dev artifact that is
   * never served to users (the production `dist/` build is 373 kB /
   * 107 kB gzip and passes the default gate untouched). The 500 kB
   * heuristic targets user-facing payloads, so it is raised HERE,
   * deliberately, for the storybook build only — not silenced
   * globally, and the app build keeps the default limit as a real
   * regression gate.
   */
  viteFinal: (viteConfig) => {
    viteConfig.build = {
      ...viteConfig.build,
      chunkSizeWarningLimit: 1800,
    };
    return viteConfig;
  },
};
export default config;
