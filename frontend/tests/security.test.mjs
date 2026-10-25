import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { containsArticle, escapeHtml } from '../src/utils/documentSafety.ts';

test('article highlighting is literal and cannot execute malformed regex', () => {
  for (const value of ['[', '(a+)+$', '.*', '\\', 'Điều 1[']) {
    assert.equal(containsArticle('Điều 12. Nội dung', value), false);
    assert.equal(containsArticle(value, value), true);
  }
  assert.equal(containsArticle('ĐIỀU 12. Nội dung', 'Điều 12'), true);
  assert.equal(containsArticle('text', null), false);
});

test('print output escapes text and metadata metacharacters', () => {
  assert.equal(escapeHtml(`<script a="x">'&</script>`),
    '&lt;script a=&quot;x&quot;&gt;&#39;&amp;&lt;/script&gt;');
  assert.equal(escapeHtml('Điều 1'), 'Điều 1');
});

test('lookup uses escaping for every untrusted print interpolation', () => {
  const source = readFileSync(new URL('../src/pages/LookupPage.tsx', import.meta.url), 'utf8');
  const print = source.split('printWindow.document.write(`')[1].split('`);')[0];
  for (const expression of print.matchAll(/\$\{([^}]+)\}/g)) {
    assert.ok(expression[1].startsWith('escapeHtml(') || expression[1].startsWith('new Date()'));
  }
  assert.ok(source.includes('containsArticle(line, highlightArticle)'));
});
