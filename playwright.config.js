// Minimal Playwright config for local e2e checks
module.exports = {
  timeout: 30 * 1000,
  use: {
    headless: true,
    viewport: { width: 1280, height: 800 }
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } }
  ],
  testDir: 'tests'
};
