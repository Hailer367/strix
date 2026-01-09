'use client'

import { Card } from '@/components/ui/card'
import { Wrench } from 'lucide-react'
import type { ToolExecution } from '@/types'

interface ToolExecutionsProps {
  tools: ToolExecution[] | undefined
}

export function ToolExecutions({ tools }: ToolExecutionsProps) {
  return (
    <Card>
      <div className="p-4 space-y-2 max-h-[400px] overflow-y-auto">
        {!tools || tools.length === 0 ? (
          <div className="text-center text-muted-foreground py-8 text-sm">
            No tool executions yet...
          </div>
        ) : (
          tools
            .slice(-50)
            .reverse()
            .map((tool, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2 rounded bg-muted/50 hover:bg-muted"
              >
                <div className="flex items-center gap-2">
                  <Wrench className="h-3 w-3 text-blue-400" />
                  <span className="text-sm text-blue-400 font-medium">{tool.tool_name}</span>
                  {tool.agent_id && (
                    <span className="text-xs text-muted-foreground">
                      by {tool.agent_id.slice(0, 8)}
                    </span>
                  )}
                </div>
                <span
                  className={
                    tool.status === 'completed'
                      ? 'text-green-400'
                      : tool.status === 'failed'
                        ? 'text-red-400'
                        : 'text-yellow-400'
                  }
                >
                  {tool.status === 'completed'
                    ? '✓'
                    : tool.status === 'failed'
                      ? '✗'
                      : '●'}
                </span>
              </div>
            ))
        )}
      </div>
    </Card>
  )
}