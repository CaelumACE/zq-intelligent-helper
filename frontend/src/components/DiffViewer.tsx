import { useState } from 'react'
import type { CompareResult } from '../types'

interface DiffViewerProps {
  result: CompareResult
  onExport: () => void
}

const LABEL: Record<string, string> = { added: '新增', removed: '删除', modified: '修改' }

export default function DiffViewer({ result, onExport }: DiffViewerProps) {
  const [filter, setFilter] = useState<'all' | 'added' | 'removed' | 'modified'>('all')
  const diffs = result.diffs.filter((d) => filter === 'all' || d.type === filter)
  const summary = result.summary

  return (
    <div className="diff-viewer">
      <div className="diff-summary">
        <span className="diff-stat added">新增 {summary.added}</span>
        <span className="diff-stat removed">删除 {summary.removed}</span>
        <span className="diff-stat modified">修改 {summary.modified}</span>
        <span className="diff-stat total">变更总数 {summary.total_changes}</span>
        <button className="diff-export" onClick={onExport}>导出 docx 报告</button>
      </div>
      {summary.brief && <div className="diff-brief">{summary.brief}</div>}

      <div className="diff-filters">
        {(['all', 'added', 'removed', 'modified'] as const).map((k) => (
          <button key={k} className={filter === k ? 'diff-filter active' : 'diff-filter'} onClick={() => setFilter(k)}>
            {k === 'all' ? '全部' : LABEL[k]}
          </button>
        ))}
      </div>

      {diffs.length === 0 && <div className="diff-empty">该筛选条件下无差异。</div>}
      {diffs.map((d, i) => (
        <div key={i} className={`diff-item ${d.type}`}>
          <div className="diff-item-head"><span className="diff-tag">{LABEL[d.type]}</span><span className="diff-clause">{d.clause || '条款'}</span></div>
          <div className="diff-pair">
            {d.old_text && <div className="diff-cell old"><div className="diff-cell-label">旧版</div><div className="diff-text">{d.old_text}</div></div>}
            {d.new_text && <div className="diff-cell new"><div className="diff-cell-label">新版</div><div className="diff-text">{d.new_text}</div></div>}
          </div>
          {d.change_note && <div className="diff-note">说明：{d.change_note}</div>}
        </div>
      ))}
    </div>
  )
}
