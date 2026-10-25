/** Treat document metadata and URL parameters as text, never code or markup. */
export function escapeHtml(value: string): string {
  const entities: Record<string, string> = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  };
  return value.replace(/[&<>"']/g, character => entities[character]);
}

export function containsArticle(line: string, article: string | null): boolean {
  return Boolean(article && line.toLocaleLowerCase('vi').includes(article.toLocaleLowerCase('vi')));
}
