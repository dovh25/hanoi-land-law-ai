import assert from 'node:assert/strict';
import { test } from 'node:test';
import { conversationReducer as reduce, initialConversations, conversationTitle } from '../src/utils/conversations.ts';

test('new conversations reuse an empty draft, do not duplicate IDs, and cap tab history', () => {
  let state = initialConversations('first');
  state = reduce(state, { type: 'new', id: 'duplicate' });
  assert.equal(state.items.length, 1);
  for (let i = 0; i < 25; i++) {
    state = reduce(state, { type: 'draft', id: state.activeId, value: `question ${i}` });
    state = reduce(state, { type: 'new', id: `id-${i}` });
  }
  assert.equal(state.items.length, 20);
  assert.equal(new Set(state.items.map(item => item.id)).size, 20);
});

test('switch, deletion and late responses preserve the correct conversation', () => {
  let state = initialConversations('a');
  state = reduce(state, { type: 'draft', id: 'a', value: 'A' });
  state = reduce(state, { type: 'new', id: 'b' });
  state = reduce(state, { type: 'messages', id: 'a', update: () => [{ id: 'm', role: 'user', text: 'First question' }] });
  assert.equal(state.activeId, 'b');
  assert.equal(conversationTitle(state.items.find(item => item.id === 'a')), 'First question');
  state = reduce(state, { type: 'select', id: 'missing' });
  assert.equal(state.activeId, 'b');
  state = reduce(state, { type: 'delete', id: 'b', replacementId: 'c' });
  assert.equal(state.activeId, 'a');
  state = reduce(state, { type: 'delete', id: 'a', replacementId: 'c' });
  assert.deepEqual(state, initialConversations('c'));
});
