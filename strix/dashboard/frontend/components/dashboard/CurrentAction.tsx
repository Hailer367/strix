import { Play, Wrench } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { CurrentStep } from '@/types'

interface CurrentActionProps {
  currentStep: CurrentStep | undefined
}

export function CurrentAction({ currentStep }: CurrentActionProps) {
  const isRunning = currentStep?.status === 'running'

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Play className="h-4 w-4" />
          Current Action
        </CardTitle>
        {isRunning && (
          <Badge variant="success" className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            Running
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        <div className="text-base font-semibold text-primary mb-1">
          {currentStep?.agent_name || 'Initializing...'}
        </div>
        <div className="text-sm text-muted-foreground mb-2 truncate">
          {currentStep?.action || 'Waiting for agent activity...'}
        </div>
        {currentStep?.tool_name && (
          <div className="flex items-center gap-2 text-xs">
            <Wrench className="h-3 w-3 text-blue-400" />
            <span className="text-blue-400">{currentStep.tool_name}</span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}