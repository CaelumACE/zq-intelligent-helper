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

/** 流式期间按纯文本渲染（保留换行），结束后再做完整 markdown 解析，避免 O(n²) */
function renderPlainText(str: string): string {
  return escapeHtml(str)
    .replace(/\n/g, '<br>')
}

export default function MarkdownContent({ content, plain = false, streaming = false }: { content: string; plain?: boolean; streaming?: boolean }) {
  const html = useMemo(() => {
    if (plain || streaming) return renderPlainText(content)
    const raw = marked.parse(content, { async: false }) as string
    const cited = raw.replace(/\[(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
    return DOMPurify.sanitize(cited, {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'sup', 'span', 'a'],
      ALLOWED_ATTR: ['href', 'title', 'class'],
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input'],
    })
  }, [content, plain, streaming])

  return <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
}
