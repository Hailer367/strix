import { AlertCircle, CheckCircle2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface ConnectionStatusProps {
  connected: boolean
  error: Error | null
}

export function ConnectionStatus({ connected, error }: ConnectionStatusProps) {
  return (
    <div className="fixed top-3 right-3 z-50">
      <Badge
        variant={connected ? 'success' : 'destructive'}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5',
          connected && 'animate-pulse-green'
        )}
      >
        {connected ? (
          <>
            <CheckCircle2 className="h-3 w-3" />
            Connected
          </>
        ) : (
          <>
            <AlertCircle className="h-3 w-3" />
            {error ? 'Error' : 'Reconnecting...'}
          </>
        )}
      </Badge>
    </div>
  )
}