import BaseCard from './BaseCard'

export interface PolicyCardData {
  /** 政策名称 */
  title: string
  /** 文号，如"京人社发〔2024〕12号" */
  doc_number?: string
  /** 发布机构 */
  issuer?: string
  /** 生效日期 YYYY-MM-DD */
  effective_date?: string
  /** 状态：现行/已废止/即将生效 */
  status?: 'active' | 'expired' | 'upcoming'
  /** 核心要点列表 */
  key_points?: string[]
  /** 政策摘要/简短描述 */
  summary?: string
  /** 关联事项名称列表 */
  related_services?: string[]
  /** 来源引用 */
  source?: string
}

export interface PolicyCardProps {
  data: PolicyCardData
  /** 点击关联事项回调 */
  onServiceClick?: (serviceName: string) => void
}

const hasText = (s?: string): s is string =>
  typeof s === 'string' && s.trim().length > 0

const STATUS_LABEL: Record<NonNullable<PolicyCardData['status']>, string> = {
  active: '现行有效',
  expired: '已废止',
  upcoming: '即将生效',
}

export default function PolicyCard({ data, onServiceClick }: PolicyCardProps) {
  const {
    title,
    doc_number,
    issuer,
    effective_date,
    status,
    key_points,
    summary,
    related_services,
    source,
  } = data

  const points = (key_points ?? []).filter(hasText).slice(0, 5)
  const services = (related_services ?? []).filter(hasText)

  const showMeta = hasText(doc_number) || hasText(issuer) || hasText(effective_date)
  const showPoints = points.length > 0
  const showServices = services.length > 0
  const showSummary = hasText(summary)
  const showSource = hasText(source)

  // 至少要有title
  if (!hasText(title)) return null

  return (
    <BaseCard
      badge="政策摘要"
      badgeVariant="policy"
      title={title}
      icon="book"
    >
      {/* 状态标签 */}
      {status && (
        <span className={`policy-status status-${status}`}>
          {STATUS_LABEL[status]}
        </span>
      )}

      {/* 元信息行：文号 | 发布机构 | 生效日期 */}
      {showMeta && (
        <div className="policy-meta">
          {hasText(doc_number) && (
            <span className="policy-meta-item">
              <span className="policy-meta-label">文号</span>
              <span className="policy-meta-value">{doc_number}</span>
            </span>
          )}
          {hasText(issuer) && (
            <span className="policy-meta-item">
              <span className="policy-meta-label">发布机构</span>
              <span className="policy-meta-value">{issuer}</span>
            </span>
          )}
          {hasText(effective_date) && (
            <span className="policy-meta-item">
              <span className="policy-meta-label">生效日期</span>
              <span className="policy-meta-value">{effective_date}</span>
            </span>
          )}
        </div>
      )}

      {/* 摘要 */}
      {showSummary && <p className="policy-summary">{summary}</p>}

      {/* 核心要点 */}
      {showPoints && (
        <section className="policy-section">
          <div className="policy-section-title">核心要点</div>
          <ul className="policy-points">
            {points.map((p, i) => (
              <li key={i}>
                <span className="policy-dot" />
                <span>{p}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 关联事项 */}
      {showServices && (
        <section className="policy-section">
          <div className="policy-section-title">关联事项</div>
          <div className="policy-services">
            {services.map((s, i) => (
              <button
                key={i}
                type="button"
                className="policy-service-chip"
                onClick={() => onServiceClick?.(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </section>
      )}

      {/* 来源 */}
      {showSource && <div className="policy-source">来源：{source}</div>}
    </BaseCard>
  )
}
