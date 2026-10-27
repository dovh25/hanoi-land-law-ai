// Run via Playwright MCP browser_run_code_unsafe(filename=absolute repository path).
// All chat responses are intercepted; no generation provider is called.
async page => {
  const checks = [], errors = [];
  const check = (value, name) => { if (!value) throw Error(name); checks.push(name); };
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error' && !/Failed to load resource.*(?:429|503)/.test(message.text())) errors.push(message.text()); });
  const base = 'http://127.0.0.1:5173';
  const info = await (await page.request.get('http://127.0.0.1:8000/api/v1/demo/info')).json();
  check(info.llm_enabled === false, 'Local Gemini disabled');
  const docs = await (await page.request.get('http://127.0.0.1:8000/api/v1/documents')).json();
  const doc = docs.items.find(item => item.ref === '88/2024/NĐ-CP') || docs.items[0];
  const fixture = {
    answer: '### Trích đoạn liên quan\n\nNội dung được tìm thấy trong Điều 11 Nghị định 88/2024/NĐ-CP. [E1]\n\n- Đối chiếu điều kiện trong văn bản gốc.\n- Kiểm tra phạm vi áp dụng trước khi sử dụng.\n\nĐây là dữ liệu kiểm thử giao diện, không phải tư vấn pháp lý.',
    status: 'llm_disabled', warnings: ['live_llm_disabled'], rejected_citations: [], llm_used: false, request_id: 'ui-test',
    corpus: { label: 'demo', validity_status: 'unknown', review_status: 'unreviewed', document_count: 2, chunk_count: 90, limitations: {}, disclaimer: 'Thông tin tham khảo' },
    sources: [{ document_id: doc.id, evidence_id: 'E1', chunk_id: 'test', document_number: doc.ref, document_title: doc.title, article_number: 'Điều 11', source_url: info.documents.find(item => item.document_number === doc.ref).source_url, source_start: 0, source_end: 100, excerpt: 'Trích đoạn kiểm thử hiển thị. Vui lòng đối chiếu văn bản chính thức.', validity_status: 'unknown', review_status: 'unreviewed', corpus_label: 'demo' }],
  };
  let mode = 'normal', release;
  await page.unroute('**/api/v1/demo/chat');
  await page.route('**/api/v1/demo/chat', async route => {
    const current = mode;
    if (current === 'delay') await new Promise(resolve => { release = resolve; });
    if (current === 'rate') return route.fulfill({ status: 429, headers: { 'Retry-After': '35', 'Access-Control-Expose-Headers': 'Retry-After' }, json: { detail: 'Chậm lại' } });
    if (current === 'error') return route.fulfill({ status: 503, json: { detail: 'Máy chủ tạm gián đoạn.' } });
    return route.fulfill({ json: { ...fixture, answer: current === 'long' ? fixture.answer + '\n\n' + Array(35).fill('Đoạn nội dung dài để kiểm tra khả năng cuộn, khoảng cách dòng và vị trí vùng soạn thảo. [E1]').join('\n\n') : fixture.answer } });
  });
  const question = () => page.getByRole('textbox', { name: 'Câu hỏi', exact: true });
  const send = async text => { await question().fill(text); await question().press('Enter'); };
  const desktopNew = () => page.locator('.desktop-sidebar .new-chat').click();
  const screenshot = name => page.screenshot({ path: `/tmp/opencode/redesign-${name}.png` });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(base); await question().waitFor();
  await page.locator('.desktop-sidebar select').selectOption('light');
  check(await page.getByRole('button', { name: 'Gửi', exact: true }).isDisabled(), 'Empty send disabled');
  check(await page.getByRole('link', { name: /Đăng nhập|Đăng ký/ }).count() === 0, 'Anonymous UI without auth controls');
  await screenshot('1440-empty-light');
  for (const [width, height] of [[390,844],[768,1024],[1440,900],[1920,1080]]) {
    await page.setViewportSize({ width, height });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Empty no overflow ${width}`);
    await screenshot(`${width}-empty-light`);
  }
  await page.setViewportSize({ width:1440,height:900 });
  await question().fill('Dòng đầu'); await question().press('Shift+Enter'); await question().press('A');
  check((await question().inputValue()).includes('\n'), 'Shift Enter multiline');
  await question().fill(Array(15).fill('Dòng câu hỏi dài').join('\n'));
  check(await question().evaluate(node => node.clientHeight <= 160 && node.clientHeight > 100), 'Composer auto resize bounded');
  await send('Điều 11 quy định gì?'); await page.locator('.source-card').waitFor();
  check(await page.locator('.prose').count() === 1, 'Enter sends and answer renders');
  check(await page.locator('.desktop-sidebar .conversation-item').count() === 1, 'One tab-local conversation');
  await page.locator('.source-excerpt summary').click();
  check(await page.locator('.source-excerpt').getAttribute('open') !== null, 'Citation expands');
  await page.locator('.prose a').first().click();
  check(await page.locator('.source-card').getAttribute('id') === (await page.locator('.prose a').first().getAttribute('href')).slice(1), 'Evidence anchor resolves');
  await screenshot('1440-active-light');
  await page.locator('.desktop-sidebar select').selectOption('dark');
  check(await page.locator('html').getAttribute('data-theme') === 'dark', 'Dark theme applied');
  await screenshot('1440-active-dark');
  await page.getByRole('button', { name: 'Thu gọn thanh bên' }).click();
  check(await page.locator('.desktop-sidebar').evaluate(node => node.clientWidth) === 64, 'Collapsed sidebar 64px');
  await page.getByRole('button', { name: 'Mở rộng thanh bên' }).click();
  check(await page.locator('.desktop-sidebar').evaluate(node => node.clientWidth) === 256, 'Expanded sidebar 256px');
  await desktopNew(); await page.getByRole('heading', { name: 'Bạn muốn tìm hiểu vấn đề đất đai nào?' }).waitFor();
  mode = 'long'; await send('Câu hỏi dài'); await page.locator('.source-card').waitFor();
  check(await page.locator('.desktop-sidebar .conversation-item').count() === 2, 'Second conversation unique');
  await page.locator('.desktop-sidebar .conversation-item').filter({ hasText: 'Điều 11 quy định gì?' }).click();
  check(await page.locator('.prose').count() === 1 && !(await page.locator('.prose').innerText()).includes('Đoạn nội dung dài'), 'Switch restores correct answer');
  await page.locator('.desktop-sidebar .conversation-item').filter({ hasText: 'Câu hỏi dài' }).click();
  for (const [width,height] of [[390,844],[768,1024],[1440,900],[1920,1080]]) {
    await page.setViewportSize({width,height});
    await page.locator('.chat-scroll').evaluate(node => { node.scrollTop = node.scrollHeight; });
    const geometry = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth > innerWidth, main: document.querySelector('.chat-scroll').getBoundingClientRect().bottom, composer: document.querySelector('.composer').getBoundingClientRect().top, last: document.querySelector('.source-card').getBoundingClientRect().bottom }));
    check(!geometry.overflow, `Long answer no overflow ${width}`);
    check(geometry.main <= geometry.composer && geometry.last <= geometry.composer, `Composer clears last source ${width}`);
    await screenshot(`${width}-long-dark`);
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Mở thanh bên',exact:true}).click();
  check(await page.locator('dialog[open]').count() === 1, 'Mobile drawer opens');
  await screenshot('390-drawer-dark');
  await page.keyboard.press('Escape'); check(await page.locator('dialog[open]').count() === 0, 'Drawer Escape closes');
  check(await page.getByRole('button',{name:'Mở thanh bên',exact:true}).evaluate(node => node === document.activeElement), 'Drawer focus restored');
  await page.getByRole('button',{name:'Mở thanh bên',exact:true}).click(); await page.mouse.click(360,400);
  check(await page.locator('dialog[open]').count() === 0, 'Drawer outside closes');
  await page.getByRole('button',{name:'Mở thanh bên',exact:true}).click();
  await page.locator('dialog[open] select').selectOption('light');
  await page.getByRole('button',{name:'Đóng thanh bên'}).click();
  await screenshot('390-active-light');
  await page.getByRole('link',{name:/Đọc Điều/}).click(); await page.locator('.legal-content').waitFor();
  check((await page.locator('.cited-provision').innerText()).startsWith('Điều 11.'), 'Reader highlights exact provision');
  check((await page.getByRole('link',{name:'Nguồn chính thức',exact:true}).getAttribute('href')).startsWith('https://'), 'Reader official source resolved');
  for (const [width,height] of [[390,844],[768,1024],[1440,900],[1920,1080]]) {
    await page.setViewportSize({width,height}); await page.locator('.reader-scroll').evaluate(node => { node.scrollTop = 0; });
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Reader no overflow ${width}`);
    await screenshot(`${width}-reader-light`);
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'Mục lục',exact:true}).click();
  check(await page.locator('.mobile-toc a').count() > 0, 'Mobile table of contents');
  await page.locator('.mobile-toc a').last().click();
  check(await page.locator('.mobile-toc').count() === 0, 'TOC selection closes menu');
  await page.getByRole('button',{name:'Thư viện văn bản',exact:true}).click(); await page.locator('.document-result').first().waitFor();
  await screenshot('390-library-light');
  for (const [width,height] of [[390,844],[768,1024],[1440,900],[1920,1080]]) {
    await page.setViewportSize({width,height});
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),`Library no overflow ${width}`);
    await screenshot(`${width}-library-light`);
  }
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('textbox',{name:'Tìm kiếm văn bản'}).fill('no-such-document-ui-test'); await page.getByRole('button',{name:'Tìm kiếm',exact:true}).click();
  await page.getByRole('heading',{name:'Không tìm thấy văn bản phù hợp'}).waitFor();check(true,'Empty search results');
  await screenshot('390-empty-results');
  await page.setViewportSize({width:1440,height:900});
  await page.locator('.desktop-sidebar a').filter({hasText:'Thư viện văn bản'}).click();
  await page.getByRole('textbox',{name:'Tìm kiếm văn bản'}).fill(''); await page.getByRole('button',{name:'Tìm kiếm',exact:true}).click();await page.locator('.document-result').first().waitFor();
  await screenshot('1440-library-light');
  const filter = page.locator('.library-filters button').nth(1);await filter.click();check(await filter.getAttribute('aria-pressed') === 'true','Type filter selected');
  await desktopNew(); mode='rate';await send('Câu hỏi giới hạn');await page.getByRole('alert').waitFor();
  check((await page.getByRole('alert').innerText()).includes('35 giây'),'Rate-limit retry header');
  check(await question().inputValue() === 'Câu hỏi giới hạn','Error restores draft');await screenshot('1440-rate-limit');
  await desktopNew();mode='error';await send('Lỗi kết nối');await page.getByRole('alert').waitFor();check(true,'API error visible');
  await desktopNew();mode='delay';await send('Đang chờ');await page.getByRole('button',{name:'Dừng trả lời'}).waitFor();
  await screenshot('1440-generating');await page.getByRole('button',{name:'Dừng trả lời'}).click();release();
  check(await page.getByRole('button',{name:'Gửi',exact:true}).count() === 1,'Cancellation restores send');
  await page.locator('.desktop-sidebar .delete-conversation').first().click();
  await page.getByRole('button',{name:'Xóa hội thoại',exact:true}).click();check(await page.locator('dialog[open]').count() === 0,'Deletion confirmation closes');
  await page.locator('.desktop-sidebar select').selectOption('dark');await page.reload();await question().waitFor();
  check(await page.locator('html').getAttribute('data-theme') === 'dark','Theme persists refresh');
  check(await page.locator('.desktop-sidebar .conversation-item').count() === 0,'Conversation history clears refresh');
  check(await page.evaluate(() => Object.keys(localStorage).every(key => key === 'hll-theme')),'Only theme persisted locally');
  await page.locator('.desktop-sidebar select').selectOption('system');
  await page.emulateMedia({colorScheme:'light'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='light');check(true,'System light respected');
  await page.emulateMedia({colorScheme:'dark'});await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');check(true,'System changes update theme');
  await page.locator('.desktop-sidebar select').selectOption('dark');
  await page.goto(base+'/lookup');await page.locator('.document-result').first().waitFor();await screenshot('1440-library-dark');
  await page.locator('.document-result').first().click();await page.locator('.legal-content').waitFor();await screenshot('1440-reader-dark');
  await page.setViewportSize({width:390,height:844});await screenshot('390-reader-dark');
  await page.goto(base);await question().waitFor();await page.setViewportSize({width:390,height:500});await question().focus();
  check(await question().evaluate(node => node.getBoundingClientRect().bottom <= innerHeight),'Composer visible in reduced mobile viewport');
  await screenshot('390-reduced-height');
  for (const path of ['/login','/register','/chat','/chat/old','/demo','/unknown']) {await page.goto(base+path);await question().waitFor();check(new URL(page.url()).pathname === '/',`Legacy redirect ${path}`);}
  check(errors.length === 0, `No browser errors: ${errors.join('; ')}`);
  return {passed:checks.length,checks,errors,screenshots:'/tmp/opencode/redesign-*.png',chat:'Deterministic intercepted responses only'};
}
