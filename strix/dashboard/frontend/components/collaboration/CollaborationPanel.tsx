'use client'

import { useState, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { CollaborationNetworkGraph } from './CollaborationNetworkGraph'
import type { Collaboration, Agent } from '@/types'
import { cn } from '@/lib/utils'

interface CollaborationPanelProps {
  collaboration: Collaboration | undefined
  agents?: Record<string, Agent> | undefined
}

export function CollaborationPanel({ collaboration, agents }: CollaborationPanelProps) {
  const [activeTab, setActiveTab] = useState('network')

  const counts = useMemo(() => {
    return {
      claims: collaboration?.claims?.length || 0,
      findings: collaboration?.findings?.length || 0,
      queue: collaboration?.work_queue?.length || 0,
      help: collaboration?.help_requests?.length || 0,
    }
  }, [collaboration])

  const getSeverityColor = (severity: string) => {
    const sev = severity.toLowerCase()
    switch (sev) {
      case 'critical':
        return 'text-red-500 font-semibold'
      case 'high':
        return 'text-orange-500'
      case 'medium':
        return 'text-yellow-500'
      case 'low':
        return 'text-green-500'
      default:
        return 'text-blue-500'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Collaboration</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="network">
              Network
            </TabsTrigger>
            <TabsTrigger value="claims">
              Claims ({counts.claims})
            </TabsTrigger>
            <TabsTrigger value="findings">
              Findings ({counts.findings})
            </TabsTrigger>
            <TabsTrigger value="queue">
              Queue ({counts.queue})
            </TabsTrigger>
            <TabsTrigger value="help">
              Help ({counts.help})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="network" className="mt-4">
            <CollaborationNetworkGraph collaboration={collaboration} agents={agents} />
          </TabsContent>

          <TabsContent value="claims" className="space-y-2 max-h-60 overflow-y-auto mt-4">
            {collaboration?.claims && collaboration.claims.length > 0 ? (
              collaboration.claims.map((claim, idx) => (
                <div key={idx} className="p-2 rounded bg-muted/50 text-sm">
                  <span className="text-primary">{claim.target}</span>
                  <span className="text-muted-foreground ml-2">[{claim.test_type}]</span>
                  <span className="text-muted-foreground ml-2 text-xs">
                    by {claim.agent_name}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-muted-foreground text-center py-4">No active claims</div>
            )}
          </TabsContent>

          <TabsContent value="findings" className="space-y-2 max-h-60 overflow-y-auto mt-4">
            {collaboration?.findings && collaboration.findings.length > 0 ? (
              collaboration.findings.map((finding, idx) => (
                <div key={idx} className="p-2 rounded bg-muted/50 text-sm">
                  <span className={cn(getSeverityColor(finding.severity || ''))}>
                    {finding.title}
                  </span>
                  <span className="text-muted-foreground ml-2">
                    [{finding.vulnerability_type}]
                  </span>
                </div>
              ))
            ) : (
              <div className="text-muted-foreground text-center py-4">No shared findings</div>
            )}
          </TabsContent>

          <TabsContent value="queue" className="space-y-2 max-h-60 overflow-y-auto mt-4">
            {collaboration?.work_queue && collaboration.work_queue.length > 0 ? (
              collaboration.work_queue.map((item, idx) => (
                <div key={idx} className="p-2 rounded bg-muted/50 text-sm">
                  <span className="text-blue-400">{item.target}</span>
                  <span className="text-muted-foreground ml-2">{item.description}</span>
                </div>
              ))
            ) : (
              <div className="text-muted-foreground text-center py-4">Work queue empty</div>
            )}
          </TabsContent>

          <TabsContent value="help" className="space-y-2 max-h-60 overflow-y-auto mt-4">
            {collaboration?.help_requests && collaboration.help_requests.length > 0 ? (
              collaboration.help_requests.map((req, idx) => (
                <div key={idx} className="p-2 rounded bg-muted/50 text-sm">
                  <span className="text-yellow-400">[{req.help_type}]</span>
                  <span className="text-foreground ml-2">{req.description}</span>
                </div>
              ))
            ) : (
              <div className="text-muted-foreground text-center py-4">No help requests</div>
            )}
          </TabsContent>
        </Tabs>

        {/* Stats */}
        <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-border">
          <div className="text-center">
            <div className="text-lg font-bold text-primary">{counts.claims}</div>
            <div className="text-xs text-muted-foreground">Claims</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-blue-400">{counts.findings}</div>
            <div className="text-xs text-muted-foreground">Findings</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-purple-400">{counts.queue}</div>
            <div className="text-xs text-muted-foreground">Queue</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-bold text-yellow-400">{counts.help}</div>
            <div className="text-xs text-muted-foreground">Help</div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}