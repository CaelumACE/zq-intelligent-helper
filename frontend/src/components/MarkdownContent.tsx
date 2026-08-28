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

/**
 * LLM 有时会把整段 Markdown 包在 ```markdown ... ``` 围栏里，
 * 导致 marked 将其渲染为 <pre><code> 代码块而非正常标题/列表。
 * 检测到整段内容被同一个 markdown 代码块包裹时，剥离围栏重新解析。
 */
function unwrapMarkdownFence(text: string): string {
  const trimmed = text.trim()
  const fenceMatch = trimmed.match(/^```(?:markdown|md)?\s*\n([\s\S]*?)\n?```\s*$/)
  if (fenceMatch) return fenceMatch[1]
  return text
}

function renderMarkdown(content: string): string {
  const unwrapped = unwrapMarkdownFence(content)
  const raw = marked.parse(unwrapped, { async: false }) as string
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

  // 依赖只用节流后的 displayContent：非流式时 displayContent 已同步等于 content，
  // 流式时每 80ms 才变一次。若把 content 放进依赖，每个 delta 都会触发重算，节流失效。
  const html = useMemo(() => {
    return renderMarkdown(displayContent)
  }, [displayContent, plain])

  return <div className="md-body" dangerouslySetInnerHTML={{ __html: html }} />
}
