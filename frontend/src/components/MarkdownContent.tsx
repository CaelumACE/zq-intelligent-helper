import { useMemo } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({
  gfm: true,
  breaks: true,
})

const escapeHtml = (str: string) =>
  str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

export default function MarkdownContent({ content, plain = false }: { content: string; plain?: boolean }) {
  const html = useMemo(() => {
    if (plain) return escapeHtml(content)
    const raw = marked.parse(content, { async: false }) as string
    const cited = raw.replace(/\[(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
    return DOMPurify.sanitize(cited, {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'sup', 'span', 'a'],
      ALLOWED_ATTR: ['href', 'title', 'class'],
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input'],
    })
  }, [content, plain])

  return <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
}
