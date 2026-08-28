import { useState, type ReactNode } from 'react'
import Icon from '../Icons'

export interface BaseCardProps {
  /** 卡片标题 */
  title?: string
  /** 左上角标签文字，如"政策摘要""办事指南" */
  badge?: string
  /** 标签颜色主题 */
  badgeVariant?: 'policy' | 'service' | 'process' | 'material' | 'compare' | 'info'
  /** 卡片描述/副标题 */
  description?: string
  /** 标题右侧图标（Icon组件name） */
  icon?: string
  /** 是否可折叠，默认false */
  collapsible?: boolean
  /** 默认展开状态，默认true */
  defaultOpen?: boolean
  /** 底部操作区按钮/链接 */
  actions?: ReactNode
  /** 自定义类名 */
  className?: string
  /** 卡片内容 */
  children: ReactNode
}

const hasText = (s?: string): s is string =>
  typeof s === 'string' && s.trim().length > 0

export default function BaseCard({
  title,
  badge,
  badgeVariant = 'info',
  description,
  icon,
  collapsible = false,
  defaultOpen = true,
  actions,
  className = '',
  children,
}: BaseCardProps) {
  const [open, setOpen] = useState(defaultOpen)

  // children 为空时不渲染空卡片
  if (!children) return null

  const showHeader = hasText(badge) || hasText(title) || icon
  const showDesc = hasText(description)
  const showActions = actions != null

  return (
    <div className={`base-card ${className}`}>
      {showHeader && (
        <div
          className={`base-card-head ${collapsible ? 'collapsible' : ''}`}
          onClick={collapsible ? () => setOpen(v => !v) : undefined}
        >
          <div className="base-card-head-left">
            {hasText(badge) && (
              <span className={`base-card-badge badge-${badgeVariant}`}>{badge}</span>
            )}
            {hasText(title) && <h4 className="base-card-title">{title}</h4>}
          </div>
          <div className="base-card-head-right">
            {icon && !collapsible && (
              <span className="base-card-icon">
                <Icon name={icon as any} size={16} />
              </span>
            )}
            {collapsible && (
              <span className={`base-card-chevron ${open ? 'open' : ''}`}>
                <Icon name="chevron-down" size={16} />
              </span>
            )}
          </div>
        </div>
      )}

      {showDesc && <p className="base-card-desc">{description}</p>}

      {(!collapsible || open) && (
        <div className="base-card-body">{children}</div>
      )}

      {showActions && (!collapsible || open) && (
        <div className="base-card-actions">{actions}</div>
      )}
    </div>
  )
}
