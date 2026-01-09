import { BarChart3 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Badge } from '@/components/ui/badge'
import type { Resources, RateLimiter } from '@/types'
import { cn } from '@/lib/utils'

interface ResourceUsageProps {
  resources: Resources | undefined
  rateLimiter: RateLimiter | undefined
}

export function ResourceUsage({ resources, rateLimiter }: ResourceUsageProps) {
  const currentRate = rateLimiter?.current_rate || 0
  const maxRate = rateLimiter?.max_rate || 60
  const ratePercentage = (currentRate / maxRate) * 100

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <BarChart3 className="h-4 w-4" />
          Resources
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Rate Limiter Status */}
        <div className="rounded-md border border-border p-3 bg-card/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">Rate Limit ({maxRate}/min)</span>
            <Badge
              variant={
                currentRate >= maxRate * 0.9
                  ? 'destructive'
                  : currentRate >= maxRate * 0.7
                    ? 'warning'
                    : 'success'
              }
            >
              {currentRate}/min
            </Badge>
          </div>
          <Progress
            value={ratePercentage}
            className={cn(
              'h-2',
              currentRate >= maxRate * 0.9 && 'bg-destructive/20',
              currentRate >= maxRate * 0.7 && currentRate < maxRate * 0.9 && 'bg-yellow-400/20'
            )}
          />
        </div>

        {/* API Calls and Cost */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-md border border-border p-3 bg-card/50 text-center">
            <div className="text-xl font-bold text-primary">
              {(resources?.api_calls || resources?.request_count || 0).toLocaleString()}
            </div>
            <div className="text-xs text-muted-foreground">API Calls</div>
          </div>
          <div className="rounded-md border border-border p-3 bg-card/50 text-center">
            <div className="text-xl font-bold text-blue-400">
              ${(resources?.total_cost || 0).toFixed(4)}
            </div>
            <div className="text-xs text-muted-foreground">Cost</div>
          </div>
        </div>

        {/* Tokens */}
        <div className="grid grid-cols-3 gap-2 text-center text-xs">
          <div>
            <div className="text-sm font-medium text-green-400">
              {(resources?.input_tokens || 0).toLocaleString()}
            </div>
            <div className="text-muted-foreground">Input</div>
          </div>
          <div>
            <div className="text-sm font-medium text-blue-400">
              {(resources?.output_tokens || 0).toLocaleString()}
            </div>
            <div className="text-muted-foreground">Output</div>
          </div>
          <div>
            <div className="text-sm font-medium text-yellow-400">
              {(resources?.cached_tokens || 0).toLocaleString()}
            </div>
            <div className="text-muted-foreground">Cached</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}