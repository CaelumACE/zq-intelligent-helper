import type { StructuredAnswer } from '../types'

interface Props {
  data: StructuredAnswer
}

const hasItems = (arr?: string[]) => Array.isArray(arr) && arr.filter(Boolean).length > 0
const hasText = (s?: string) => typeof s === 'string' && s.trim().length > 0

export default function ServiceCard({ data }: Props) {
  const {
    item_name,
    description,
    required_materials,
    steps,
    location,
    time_limit,
    fee,
    consult_phone,
  } = data

  const showMaterials = hasItems(required_materials)
  const showSteps = hasItems(steps)
  const showMeta = hasText(location) || hasText(time_limit) || hasText(fee) || hasText(consult_phone)
  const empty = !showMaterials && !showSteps && !showMeta && !hasText(description)

  if (empty) return null

  return (
    <div className="service-card">
      <div className="svc-head">
        <span className="svc-badge">办事指南</span>
        {hasText(item_name) && <h4 className="svc-title">{item_name}</h4>}
      </div>

      {hasText(description) && (
        <p className="svc-desc">{description}</p>
      )}

      {showMaterials && (
        <section className="svc-section">
          <div className="svc-section-title">
            <span className="svc-icon">📋</span> 所需材料
          </div>
          <ul className="svc-list svc-materials">
            {required_materials!.filter(Boolean).map((m, i) => (
              <li key={i}>
                <span className="svc-check" />
                <span>{m}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {showSteps && (
        <section className="svc-section">
          <div className="svc-section-title">
            <span className="svc-icon">📝</span> 办理流程
          </div>
          <ol className="svc-list svc-steps">
            {steps!.filter(Boolean).map((s, i) => (
              <li key={i}>
                <span className="svc-step-num">{i + 1}</span>
                <span>{s}</span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {showMeta && (
        <section className="svc-meta-grid">
          {hasText(location) && (
            <div className="svc-meta-item">
              <span className="svc-meta-icon">📍</span>
              <div>
                <div className="svc-meta-label">办理地点</div>
                <div className="svc-meta-value">{location}</div>
              </div>
            </div>
          )}
          {hasText(time_limit) && (
            <div className="svc-meta-item">
              <span className="svc-meta-icon">⏰</span>
              <div>
                <div className="svc-meta-label">办理时限</div>
                <div className="svc-meta-value">{time_limit}</div>
              </div>
            </div>
          )}
          {hasText(fee) && (
            <div className="svc-meta-item">
              <span className="svc-meta-icon">💰</span>
              <div>
                <div className="svc-meta-label">收费标准</div>
                <div className="svc-meta-value">{fee}</div>
              </div>
            </div>
          )}
          {hasText(consult_phone) && (
            <div className="svc-meta-item">
              <span className="svc-meta-icon">📞</span>
              <div>
                <div className="svc-meta-label">咨询电话</div>
                <div className="svc-meta-value svc-phone">{consult_phone}</div>
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
