/** Treat document metadata and URL parameters as text, never code or markup. */
export function escapeHtml(value: string): string {
  const entities: Record<string, string> = {
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  };
  return value.replace(/[&<>"']/g, character => entities[character]);
}

export function containsArticle(line: string, article: string | null): boolean {
  if (!article || !/^Điều\s+\d+[a-zđ]?$/iu.test(article)) return false;
  return line.trim().toLocaleLowerCase('vi').startsWith(article.toLocaleLowerCase('vi'))
    && !/[\da-zđ]/iu.test(line.trim().slice(article.length, article.length + 1));
}

export function safeSourceUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && !url.username && !url.password ? url.href : undefined;
  } catch { return undefined; }
}
