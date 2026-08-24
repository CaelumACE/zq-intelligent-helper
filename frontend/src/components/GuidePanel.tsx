import { useState } from 'react'
import type { GuideTheme } from '../types'
import GuideHome from './GuideHome'
import Roadmap from './Roadmap'

interface GuidePanelProps {
  token: string | null
  onRequireLogin: () => void
}

export default function GuidePanel({ token, onRequireLogin }: GuidePanelProps) {
  const [activeTheme, setActiveTheme] = useState<GuideTheme | null>(null)

  if (activeTheme) {
    return (
      <Roadmap
        themeId={activeTheme.id}
        themeName={activeTheme.name}
        icon={activeTheme.icon}
        totalDays={activeTheme.estimated_days}
        token={token}
        onBack={() => setActiveTheme(null)}
        onRequireLogin={onRequireLogin}
      />
    )
  }

  return <GuideHome onOpenTheme={(themeId) => setActiveTheme({ id: themeId } as GuideTheme)} />
}
