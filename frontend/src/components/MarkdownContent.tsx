import { useMemo, useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({
  gfm: true,
  breaks: true,
})

/** 将引用标记 [n] 转为上标样式 */
function citeReplacer(_: string, n: string): string {
  return `<sup class="cite">${n}</sup>`
}

function renderMarkdown(content: string): string {
  const raw = marked.parse(content, { async: false }) as string
  const cited = raw.replace(/\[(\d+)\]/g, citeReplacer)
  return DOMPurify.sanitize(cited, {
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'u', 's', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'pre', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'hr', 'sup', 'span', 'a'],
    ALLOWED_ATTR: ['href', 'title', 'class'],
    ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
    FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input'],
  })
}

/** 流式渲染：节流 80ms 更新一次 markdown，既避免 O(n²) 又实时显示格式 */
function useThrottledContent(content: string, streaming: boolean, interval = 80): string {
  const [throttled, setThrottled] = useState(content)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastUpdate = useRef(0)

  useEffect(() => {
    if (!streaming) {
      setThrottled(content)
      return
    }
    const now = Date.now()
    const elapsed = now - lastUpdate.current
    if (elapsed >= interval) {
      lastUpdate.current = now
      setThrottled(content)
    } else if (!timer.current) {
      timer.current = setTimeout(() => {
        lastUpdate.current = Date.now()
        timer.current = null
        setThrottled(content)
      }, interval - elapsed)
    }
    return () => {
      if (timer.current) {
        clearTimeout(timer.current)
        timer.current = null
      }
    }
  }, [content, streaming, interval])

  // 流结束时立即用最终内容
  useEffect(() => {
    if (!streaming) setThrottled(content)
  }, [streaming, content])

  return throttled
}

export default function MarkdownContent({ content, plain = false, streaming = false }: { content: string; plain?: boolean; streaming?: boolean }) {
  const displayContent = useThrottledContent(content, streaming)

  const html = useMemo(() => {
    if (plain) return renderMarkdown(content)
    return renderMarkdown(displayContent)
  }, [displayContent, plain, content])

  return <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
}
