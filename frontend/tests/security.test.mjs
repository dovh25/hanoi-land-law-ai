import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { containsArticle, escapeHtml, safeSourceUrl } from '../src/utils/documentSafety.ts';

test('article highlighting is literal and cannot execute malformed regex', () => {
  for (const value of ['[', '(a+)+$', '.*', '\\', 'Điều 1[']) {
    assert.equal(containsArticle('Điều 12. Nội dung', value), false);
    assert.equal(containsArticle(value, value), false);
  }
  assert.equal(containsArticle('ĐIỀU 12. Nội dung', 'Điều 12'), true);
  assert.equal(containsArticle('text', null), false);
  assert.equal(containsArticle('Điều 12. Nội dung', 'Điều 1'), false);
});

test('source links reject executable schemes and credentials', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,hi', 'https://user:pass@example.org', '/login']) {
    assert.equal(safeSourceUrl(url), undefined);
  }
  assert.equal(safeSourceUrl('https://vanban.chinhphu.vn/?docid=1'), 'https://vanban.chinhphu.vn/?docid=1');
});

test('print output escapes text and metadata metacharacters', () => {
  assert.equal(escapeHtml(`<script a="x">'&</script>`),
    '&lt;script a=&quot;x&quot;&gt;&#39;&amp;&lt;/script&gt;');
  assert.equal(escapeHtml('Điều 1'), 'Điều 1');
});

test('lookup uses escaping for every untrusted print interpolation', () => {
  const source = readFileSync(new URL('../src/pages/LookupPage.tsx', import.meta.url), 'utf8');
  const print = source.split('popup.document.write(`')[1].split('`);')[0];
  for (const expression of print.matchAll(/\$\{([^}]+)\}/g)) {
    assert.ok(expression[1].startsWith('escapeHtml(') || expression[1].startsWith('new Date()'));
  }
  assert.ok(source.includes('containsArticle(line, article)'));
});
