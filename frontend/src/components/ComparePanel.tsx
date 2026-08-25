import { useState } from 'react'
import CompareHome from './CompareHome'
import KnowledgeAdmin from './KnowledgeAdmin'
import SearchTester from './SearchTester'

interface ComparePanelProps {
  token: string | null
  userRole: string | undefined
  onRequireLogin: () => void
}

export default function ComparePanel({ token, userRole, onRequireLogin }: ComparePanelProps) {
  const [view, setView] = useState<'compare' | 'admin' | 'tester'>('compare')

  return (
    <div className="compare-panel">
      <div className="compare-tabs">
        <button className={view === 'compare' ? 'app-tab active' : 'app-tab'} onClick={() => setView('compare')}>政策比对</button>
        <button className={view === 'admin' ? 'app-tab active' : 'app-tab'} onClick={() => setView('admin')} style={{ display: userRole === 'admin' || userRole === 'super_admin' ? 'inline-block' : 'none' }}>知识库后台</button>
        <button className={view === 'tester' ? 'app-tab active' : 'app-tab'} onClick={() => setView('tester')}>检索测试</button>
      </div>
      {view === 'compare' && <CompareHome token={token} onRequireLogin={onRequireLogin} />}
      {view === 'admin' && <KnowledgeAdmin userRole={userRole} />}
      {view === 'tester' && <SearchTester />}
    </div>
  )
}
