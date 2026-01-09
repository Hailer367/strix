import { Clock } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { formatDuration } from '@/lib/utils'
import type { TimeInfo } from '@/types'
import { cn } from '@/lib/utils'

interface TimeProgressProps {
  time: TimeInfo | undefined
}

export function TimeProgress({ time }: TimeProgressProps) {
  const progress = time?.progress_percentage || 0
  const isWarning = time?.is_warning
  const isCritical = time?.is_critical

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Clock className="h-4 w-4" />
          Time Remaining
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={cn(
            'text-xl font-bold mb-2',
            isCritical ? 'text-destructive' : isWarning ? 'text-yellow-400' : 'text-primary'
          )}
        >
          {time?.status || 'Starting...'}
        </div>
        <Progress
          value={progress}
          className={cn(
            'h-2 mb-3',
            isCritical && 'bg-destructive/20',
            isWarning && 'bg-yellow-400/20'
          )}
        />
        <div className="grid grid-cols-2 gap-4 text-xs">
          <div>
            <span className="text-muted-foreground">Elapsed</span>
            <div className="text-foreground font-medium">
              {formatDuration(time?.elapsed_minutes || 0)}
            </div>
          </div>
          <div>
            <span className="text-muted-foreground">Remaining</span>
            <div className="text-foreground font-medium">
              {formatDuration(time?.remaining_minutes || 0)}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}