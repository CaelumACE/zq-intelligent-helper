import { useState } from 'react'
import type { ModelProvider } from '../types'

interface WritingPanelProps {
  open: boolean
  onClose: () => void
  onGenerate: (prompt: string, model: ModelProvider) => void
  model: ModelProvider
}

const DOC_TYPES = ['通知', '纪要', '报告', '请示']

export default function WritingPanel({ open, onClose, onGenerate, model }: WritingPanelProps) {
  const [docType, setDocType] = useState('通知')
  const [title, setTitle] = useState('')
  const [to, setTo] = useState('')
  const [body, setBody] = useState('')
  const [sign, setSign] = useState('')
  const [generating, setGenerating] = useState(false)

  const handleGenerate = () => {
    if (!title.trim() || !body.trim() || generating) return
    const prompt = `请帮我撰写一份${docType}。标题：${title}；主送单位：${to || '未指定'}；正文要点：${body}；落款：${sign || '未指定'}。请严格按照公文格式生成。`
    setGenerating(true)
    window.setTimeout(() => setGenerating(false), 2500)
    onGenerate(prompt, model)
  }

  return (
    <div className={`doc-panel ${open ? 'open' : ''}`}>
      <div className="doc-head">
        <h3>✍️ 公文写作助手</h3>
        <span className="doc-close" onClick={onClose}>✕</span>
      </div>
      <div className="doc-tabs">
        {DOC_TYPES.map((type) => (
          <button
            key={type}
            className={`doc-tab ${docType === type ? 'active' : ''}`}
            onClick={() => setDocType(type)}
          >
            {type}
          </button>
        ))}
      </div>
      <div className="doc-form">
        <div className="doc-field">
          <label>标题<span className="req"> *</span></label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="如：关于召开2026年度工作会议的通知" />
        </div>
        <div className="doc-field">
          <label>主送单位</label>
          <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="如：机关各处室、各直属单位" />
        </div>
        <div className="doc-field">
          <label>正文要点<span className="req"> *</span></label>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="输入会议时间、地点、参会人员、会议内容等要点…" />
        </div>
        <div className="doc-field">
          <label>落款单位 / 日期</label>
          <input value={sign} onChange={(e) => setSign(e.target.value)} placeholder="如：办公室 · 2026年8月22日" />
        </div>
        <button className="gen-btn" disabled={generating} onClick={handleGenerate}>
          {generating ? '生成中…' : '生成初稿'}
        </button>
      </div>
    </div>
  )
}
