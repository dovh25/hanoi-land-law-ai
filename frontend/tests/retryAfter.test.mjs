import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseRetryAfter } from '../src/utils/retryAfter.ts';

test('rate-limit header preserves positive delay seconds', () => {
  assert.equal(parseRetryAfter('47'), 47);
});

test('missing or invalid rate-limit header uses fallback, never zero seconds', () => {
  for (const value of [null, '', ' ', '0', '-1', 'NaN', '1.5', 'Infinity']) {
    assert.equal(parseRetryAfter(value), null);
  }
});
