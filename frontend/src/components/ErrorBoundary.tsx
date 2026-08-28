import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

/**
 * 顶层错误边界：避免任一子组件渲染抛错导致整页白屏（政务演示现场致命）。
 * 必须写成类组件（React 错误边界 API 仅类组件支持）。
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error('UI 渲染异常：', error, info)
  }

  handleReload = () => {
    this.setState({ hasError: false })
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="error-boundary">
            <div className="error-boundary-card">
              <div className="error-boundary-icon">⚠️</div>
              <h2>页面出现异常</h2>
              <p>当前页面渲染出错，可尝试刷新恢复。若反复出现，请联系系统管理员。</p>
              <pre className="error-boundary-detail">{this.state.error?.message}</pre>
              <button className="error-boundary-btn" onClick={this.handleReload}>
                刷新页面
              </button>
            </div>
          </div>
        )
      )
    }
    return this.props.children
  }
}
