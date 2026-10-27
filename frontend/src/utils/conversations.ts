import type { DemoMessage } from '../types/demo';

/** UI identifiers only: never sent as server ownership credentials. */
export function newId(): string { return crypto.randomUUID(); }

export interface Conversation {
  id: string;
  messages: DemoMessage[];
  draft: string;
}

export interface ConversationState { items: Conversation[]; activeId: string }
export type ConversationAction =
  | { type: 'new'; id: string }
  | { type: 'select'; id: string }
  | { type: 'delete'; id: string; replacementId: string }
  | { type: 'draft'; id: string; value: string }
  | { type: 'messages'; id: string; update: (messages: DemoMessage[]) => DemoMessage[] };

export function initialConversations(id: string): ConversationState {
  return { items: [{ id, messages: [], draft: '' }], activeId: id };
}

export function conversationTitle(item: Conversation): string {
  return (item.messages.find(message => message.role === 'user')?.text || item.draft || 'Hội thoại mới').split('\n')[0].slice(0, 64);
}

export function conversationReducer(state: ConversationState, action: ConversationAction): ConversationState {
  if (action.type === 'new') {
    const empty = state.items.find(item => !item.messages.length && !item.draft);
    if (empty) return { ...state, activeId: empty.id };
    return { items: [{ id: action.id, messages: [], draft: '' }, ...state.items].slice(0, 20), activeId: action.id };
  }
  if (action.type === 'select') {
    return state.items.some(item => item.id === action.id) ? { ...state, activeId: action.id } : state;
  }
  if (action.type === 'delete') {
    const items = state.items.filter(item => item.id !== action.id);
    if (!items.length) return initialConversations(action.replacementId);
    return { items, activeId: action.id === state.activeId ? items[0].id : state.activeId };
  }
  return { ...state, items: state.items.map(item => item.id !== action.id ? item : action.type === 'draft'
    ? { ...item, draft: action.value.slice(0, 1000) }
    : { ...item, messages: action.update(item.messages) }) };
}
