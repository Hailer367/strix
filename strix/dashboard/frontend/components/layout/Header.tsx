import { Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { ExportButton } from '@/components/export/ExportButton'
import { formatTime } from '@/lib/utils'

interface HeaderProps {
  lastUpdate: string | null | undefined
  scanConfig: Record<string, any> | undefined
}

export function Header({ lastUpdate, scanConfig }: HeaderProps) {
  const target =
    scanConfig?.targets?.[0]?.details?.target_url ||
    scanConfig?.targets?.[0]?.details?.target_repo ||
    scanConfig?.targets?.[0]?.original ||
    'No target'

  return (
    <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-40">
      <div className="container mx-auto px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🦉</span>
          <div>
            <h1 className="text-lg font-bold text-primary flex items-center gap-2">
              Strix Security Dashboard
              <Badge variant="success">Live</Badge>
            </h1>
            <p className="text-xs text-muted-foreground truncate max-w-md" title={String(target)}>
              Target: {String(target)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>Last update: {formatTime(lastUpdate)}</span>
          </div>
          <ExportButton />
        </div>
      </div>
    </header>
  )
}