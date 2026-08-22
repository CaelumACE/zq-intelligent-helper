import { useMemo } from 'react'
import { marked } from 'marked'

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
    return raw.replace(/\[(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
  }, [content, plain])

  return <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
}
