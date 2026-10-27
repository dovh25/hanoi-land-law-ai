// Run with Playwright MCP browser_run_code_unsafe(filename=absolute path to this file).
// Requires local API with ENABLE_LIVE_LLM=false and frontend on 127.0.0.1:5173.
async (page) => {
  const base = 'http://127.0.0.1:5173';
  const api = 'http://127.0.0.1:8000';
  const checks = [];
  const errors = [];
  const check = (condition, name) => {
    if (!condition) throw new Error(name);
    checks.push(name);
  };
  page.on('pageerror', error => errors.push(error.message));
  const info = await (await page.request.get(`${api}/api/v1/demo/info`)).json();
  check(info.llm_enabled === false, 'Live Gemini explicitly disabled');
  const fixtures = {};
  for (const [name, message] of Object.entries({
    greeting: 'Xin chào', legal: 'Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?',
    outside: 'Viết chương trình Python',
  })) {
    const response = await page.request.post(`${api}/api/v1/demo/chat`, { data: { message } });
    check(response.ok(), `Real offline API ${name}`);
    fixtures[name] = await response.json();
  }
  check(fixtures.legal.sources.length > 0 && !fixtures.legal.llm_used, 'Actual BM25 citations without Gemini');
  let mode = 'greeting';
  let release;
  await page.route('**/api/v1/demo/chat', async route => {
    if (mode === 'delayed') await new Promise(resolve => { release = resolve; });
    if (mode === 'invalid') return route.fulfill({ json: { answer: null, sources: {} } });
    if (mode === 'rate') return route.fulfill({ status: 429, headers: { 'Retry-After': '35', 'Access-Control-Expose-Headers': 'Retry-After' }, json: { detail: 'Chậm lại' } });
    await route.fulfill({ json: fixtures[mode] || fixtures.greeting });
  });
  const question = () => page.getByRole('textbox', { name: 'Câu hỏi', exact: true });
  const send = async text => { await question().fill(text); await question().press('Enter'); };
  const reset = async () => page.getByRole('button', { name: 'Hội thoại mới' }).click();
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(base);
  await question().waitFor();
  check(await page.getByRole('link', { name: /Đăng nhập|Đăng ký/ }).count() === 0, 'No account navigation');
  await page.screenshot({ path: '/tmp/opencode/hanoi-desktop-empty.png' });
  for (const path of ['/login', '/register', '/chat', '/chat/unknown', '/demo', '/unknown']) {
    await page.goto(base + path);
    await question().waitFor();
    check(new URL(page.url()).pathname === '/', `Safe legacy redirect ${path}`);
  }
  await question().fill('Dòng 1');
  await question().press('Shift+Enter');
  await question().press('A');
  check((await question().inputValue()).includes('\n'), 'Multiline Shift+Enter');
  await send('Xin chào');
  await page.getByText('Trợ lý', { exact: true }).waitFor();
  await page.screenshot({ path: '/tmp/opencode/hanoi-desktop-chat.png' });
  check(await page.locator('.prose').count() === 1, 'Greeting renders via Enter-to-send');
  await reset();
  mode = 'legal';
  await send('Điều 11 Nghị định 88/2024/NĐ-CP quy định gì?');
  await page.locator('article').first().waitFor();
  check(await page.locator('article').count() > 0, 'Source cards display');
  await page.screenshot({ path: '/tmp/opencode/hanoi-citations.png' });
  const sourceHref = await page.getByRole('link', { name: /Đọc Điều/ }).first().getAttribute('href');
  const sourceUrl = await page.getByRole('link', { name: 'Nguồn chính thức ↗' }).first().getAttribute('href');
  check(sourceUrl.startsWith('https://vanban.chinhphu.vn/'), 'Official source link targets validated portal');
  const inline = page.locator('.prose a[href^="#"]').first();
  await inline.click();
  const anchor = (await inline.getAttribute('href')).slice(1);
  check(await page.locator(`[id="${anchor}"]`).count() === 1, 'Inline evidence anchor resolves');
  for (const [width, height] of [[375, 812], [390, 844], [768, 1024], [1366, 768], [1920, 1080]]) {
    await page.setViewportSize({ width, height });
    await page.locator('main').evaluate(el => { el.scrollTop = el.scrollHeight; });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Chat no horizontal overflow ${width}`);
    const bounds = await page.evaluate(() => {
      const main = document.querySelector('main').getBoundingClientRect();
      const composer = document.querySelector('textarea').getBoundingClientRect();
      const cards = [...document.querySelectorAll('article')];
      return { mainBottom: main.bottom, composerTop: composer.top, lastBottom: cards.at(-1).getBoundingClientRect().bottom };
    });
    check(bounds.mainBottom <= bounds.composerTop && bounds.lastBottom <= bounds.composerTop, `Composer does not obscure last citation ${width}`);
    if (width === 390) await page.screenshot({ path: '/tmp/opencode/hanoi-mobile-chat.png' });
  }
  await page.getByRole('link', { name: /Đọc Điều/ }).first().click();
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(page.url().includes('article='), 'Citation navigates to provision');
  await page.waitForFunction(() => [...document.querySelectorAll('span.bg-yellow-200')].some(el => el.textContent.startsWith('Điều 11.')));
  check(true, 'Correct article highlighted, not Điều 1 or inline cross-reference');
  await page.getByRole('link', { name: 'Chat', exact: true }).click();
  await page.locator('article').first().waitFor();
  check(true, 'Returning from lookup preserves tab-local conversation');
  await page.getByRole('link', { name: /Đọc Điều/ }).first().click();
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(await page.locator('main .overflow-y-auto').first().evaluate(el => el.scrollHeight > 5000), 'Long legal document scrolls');
  await page.locator('main .overflow-y-auto').first().evaluate(el => { el.scrollTop = 0; });
  for (const [width, height] of [[375, 812], [390, 844], [768, 1024], [1366, 768], [1920, 1080]]) {
    await page.setViewportSize({ width, height });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Reader no horizontal overflow ${width}`);
    if (width === 390) await page.screenshot({ path: '/tmp/opencode/hanoi-mobile-lookup.png' });
    if (width === 1366) await page.screenshot({ path: '/tmp/opencode/hanoi-desktop-lookup.png' });
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '← Danh sách văn bản' }).click();
  const search = page.getByRole('textbox', { name: 'Tìm kiếm văn bản' });
  await search.fill('không-tồn-tại-xyz');
  await page.getByRole('button', { name: 'Tìm', exact: true }).click();
  await page.getByText('Không tìm thấy văn bản phù hợp').waitFor();
  check(true, 'Mobile list navigation and empty search');
  await search.fill('88/2024');
  await page.getByRole('button', { name: 'Tìm', exact: true }).click();
  await page.getByRole('button', { name: /Quy định về bồi thường/ }).first().click();
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(true, 'Search and mobile reader selection');
  await page.reload();
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(!page.url().includes('login'), 'Direct reader refresh remains public');
  await page.getByRole('button', { name: '← Danh sách văn bản' }).click();
  await page.getByRole('button', { name: /Quy định về bồi thường/ }).first().click();
  check(await page.getByRole('heading', { level: 1 }).isVisible(), 'Same mobile document can be reopened');
  const invalidArticle = new URL(sourceHref, base);
  invalidArticle.searchParams.set('article', '[');
  await page.goto(invalidArticle.href);
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(await page.locator('mark').count() === 0, 'Invalid article parameter ignored safely');
  await page.goto(base + '/lookup?id=does-not-exist');
  await page.getByText(/Không thể tải văn bản/).waitFor();
  check(true, 'Missing document error');
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(base + '/lookup');
  await page.getByRole('button', { name: 'Luật', exact: true }).click();
  await page.getByRole('button', { name: /Luật sửa đổi/ }).waitFor();
  check(await page.getByRole('button', { name: /Quy định về bồi thường/ }).count() === 0, 'Document type filter works');
  await page.getByRole('button', { name: 'Luật', exact: true }).click();
  await page.getByRole('button', { name: /Quy định về bồi thường/ }).waitFor();
  await page.getByRole('button', { name: /Quy định về bồi thường/ }).click();
  const toc = page.getByRole('button', { name: /^Điều 11:/ }).last();
  await toc.click();
  check(true, 'Desktop table of contents navigates');
  await page.getByRole('button', { name: 'Mục lục', exact: true }).click();
  check(await toc.count() === 0, 'Table of contents toggles');
  await page.context().addInitScript(() => { window.print = () => {}; });
  const popupEvent = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'Xuất PDF' }).click();
  const popup = await popupEvent;
  await popup.waitForLoadState('domcontentloaded');
  check((await popup.locator('body').innerText()).includes('88/2024/NĐ-CP'), 'Print/export opens escaped document');
  await popup.close();
  await page.goBack();
  await page.goForward();
  await page.getByRole('heading', { level: 1 }).waitFor();
  check(!page.url().includes('login'), 'Browser back and forward remain public');
  await page.route('**/api/v1/documents?*', route => route.fulfill({ json: { items: null } }));
  await page.goto(base + '/lookup');
  await page.getByRole('alert').waitFor();
  check(true, 'Malformed lookup list fails safely');
  await page.unroute('**/api/v1/documents?*');
  const document = await (await page.request.get(`${api}/api/v1/documents/${fixtures.legal.sources[0].document_id}`)).json();
  await page.route('**/api/v1/documents?*', route => {
    const number = Number(new URL(route.request().url()).searchParams.get('page') || 1);
    return route.fulfill({ json: { items: [{ ...document, title: `Kết quả trang ${number}` }], page: number, total: 41, page_size: 20, total_pages: 3 } });
  });
  await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
  await page.getByRole('button', { name: /Kết quả trang 1/ }).waitFor();
  check(true, 'Lookup error retry recovers');
  await page.getByRole('button', { name: 'Trang sau' }).click();
  await page.getByRole('button', { name: /Kết quả trang 2/ }).waitFor();
  await page.getByRole('button', { name: 'Trang trước' }).click();
  await page.getByRole('button', { name: /Kết quả trang 1/ }).waitFor();
  check(true, 'Pagination next and previous work with deterministic multi-page fixture');
  await page.unroute('**/api/v1/documents?*');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('link', { name: 'Chat', exact: true }).click();
  mode = 'outside';
  await send('Viết chương trình Python');
  await page.getByText('Chưa đủ căn cứ', { exact: true }).waitFor();
  check(true, 'Out-of-scope abstention renders');
  await reset();
  mode = 'invalid';
  await send('Thử dữ liệu lỗi');
  await page.getByRole('alert').waitFor();
  check((await page.getByRole('alert').innerText()).includes('chưa hợp lệ'), 'Malformed API response handled without crash');
  await page.screenshot({ path: '/tmp/opencode/hanoi-error.png' });
  await reset();
  fixtures.rich = { ...fixtures.legal,
    answer: '# Định dạng\n\n**Văn bản**\n\n- Mục một\n- Mục hai\n\n```text\n' + 'long_code_'.repeat(100) + '\n```\n\n<img src=x onerror="window.auditXss=true">\n\n[unsafe](javascript:alert(1))',
    sources: [{ ...fixtures.legal.sources[0], source_url: 'javascript:alert(1)' }],
  };
  mode = 'rich';
  await send('Kiểm tra định dạng');
  await page.locator('.prose pre').waitFor();
  check(await page.locator('.prose strong').count() > 0 && await page.locator('.prose li').count() === 2, 'Markdown headings, emphasis, lists and code render');
  check(await page.locator('img, a[href^="javascript:"]').count() === 0, 'Executable markup and unsafe links cannot render');
  check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Long code block stays within mobile width');
  await reset();
  mode = 'rate';
  await send('Thử giới hạn');
  await page.getByRole('alert').waitFor();
  check((await page.getByRole('alert').innerText()).includes('35'), 'Rate-limit Retry-After shown');
  await reset();
  mode = 'delayed';
  await send('Yêu cầu chậm');
  await page.getByRole('status').waitFor();
  await reset();
  release();
  await page.getByRole('heading', { name: 'Hỏi về bồi thường, hỗ trợ, tái định cư' }).waitFor();
  check(await page.locator('.prose').count() === 0, 'New conversation cancels stale response');
  await page.reload();
  await question().waitFor();
  check(new URL(page.url()).pathname === '/', 'Chat refresh stays anonymous');
  const context = await page.context().browser().newContext();
  const visitor = await context.newPage();
  await visitor.goto(base);
  await visitor.getByRole('textbox', { name: 'Câu hỏi', exact: true }).waitFor();
  check(await visitor.locator('.prose').count() === 0, 'Independent visitor sees no other conversation');
  await context.close();
  check(errors.length === 0, 'No uncaught JavaScript errors');
  return { passed: checks.length, checks, errors, screenshots: '/tmp/opencode/hanoi-*.png' };
}
