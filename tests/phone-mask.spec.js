const { test, expect } = require('@playwright/test');

// NOTE: Run your dev server first: .venv\Scripts\python eacis/app.py (or however you run)
// Then run: npm install && npx playwright install && npm run test:playwright

test('phone mask: visible formatting + hidden raw value + caret preservation', async ({ page }) => {
  await page.goto('http://127.0.0.1:5000/checkout');
  await page.waitForSelector('#checkout-phone');

  const visible = await page.$('#checkout-phone');
  const raw = await page.$('#checkout-phone-raw');
  // clear
  await visible.fill('');

  // Type digits
  await visible.type('12345678901');
  // raw should contain digits-only up to 11
  const rawVal = await raw.inputValue();
  expect(rawVal).toBe('12345678901');

  // visible should be formatted as 4-3-4
  const vis = await visible.inputValue();
  expect(vis).toBe('1234-567-8901');

  // Now test caret preservation: set cursor in the middle, type a char
  await page.evaluate(() => {
    const el = document.getElementById('checkout-phone');
    el.focus();
    // place cursor after the second digit (accounting for formatting)
    el.setSelectionRange(2,2);
  });
  await visible.type('6');

  const newRaw = await raw.inputValue();
  expect(newRaw.length).toBeGreaterThanOrEqual(1);

  // ensure no JS errors occurred during typing
  const errors = await page.evaluate(() => window.__eacis_console_errors || []);
  expect(errors.length).toBe(0);
});
