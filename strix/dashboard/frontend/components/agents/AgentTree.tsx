'use client'

import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { Agent } from '@/types'
import { cn } from '@/lib/utils'

interface AgentTreeProps {
  agents: Record<string, Agent> | undefined
}

export function AgentTree({ agents }: AgentTreeProps) {
  const agentList = Object.values(agents || {})
  const rootAgents = agentList.filter((a) => !a.parent_id)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-green-500 animate-pulse'
      case 'waiting':
        return 'bg-yellow-500'
      case 'completed':
        return 'bg-blue-500'
      case 'failed':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  const renderAgent = (agent: Agent, depth = 0) => {
    const children = agentList.filter((a) => a.parent_id === agent.id)

    return (
      <div key={agent.id} className={depth > 0 ? 'ml-4 border-l-2 border-border pl-2' : ''}>
        <div className="flex items-center gap-2 py-2 px-3 rounded hover:bg-muted/50">
          <span className={cn('w-2 h-2 rounded-full', getStatusColor(agent.status))} />
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-foreground truncate">
              {agent.name || 'Agent'}
            </div>
            {agent.task && (
              <div className="text-xs text-muted-foreground truncate">{agent.task}</div>
            )}
          </div>
          <Badge
            variant={
              agent.status === 'running'
                ? 'success'
                : agent.status === 'completed'
                  ? 'info'
                  : agent.status === 'failed'
                    ? 'destructive'
                    : 'secondary'
            }
          >
            {agent.status}
          </Badge>
        </div>
        {children.length > 0 && (
          <div className="ml-2">{children.map((child) => renderAgent(child, depth + 1))}</div>
        )}
      </div>
    )
  }

  return (
    <Card>
      <div className="p-4">
        {rootAgents.length === 0 ? (
          <div className="text-center text-muted-foreground py-8 text-sm">
            No agents running yet...
          </div>
        ) : (
          <div className="space-y-1">{rootAgents.map((agent) => renderAgent(agent))}</div>
        )}
      </div>
    </Card>
  )
}