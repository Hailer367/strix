'use client'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TimeProgress } from '@/components/dashboard/TimeProgress'
import { CurrentAction } from '@/components/dashboard/CurrentAction'
import { ResourceUsage } from '@/components/dashboard/ResourceUsage'
import { CLITerminal } from '@/components/terminal/CLITerminal'
import { AgentTree } from '@/components/agents/AgentTree'
import { CollaborationPanel } from '@/components/collaboration/CollaborationPanel'
import { ToolExecutions } from '@/components/tools/ToolExecutions'
import { VulnerabilityPanel } from '@/components/vulnerabilities/VulnerabilityPanel'
import type { DashboardState } from '@/types'

interface DashboardContentProps {
  state: DashboardState
}

export function DashboardContent({ state }: DashboardContentProps) {
  return (
    <div className="space-y-4">
      {/* Top Row - Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <TimeProgress time={state.time} />
        <CurrentAction currentStep={state.current_step} />
        <ResourceUsage resources={state.resources} rateLimiter={state.rate_limiter} />
      </div>

      {/* Main Content Row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2">
          <Tabs defaultValue="terminal" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="terminal">AI Terminal</TabsTrigger>
              <TabsTrigger value="agents">Agents</TabsTrigger>
              <TabsTrigger value="collaboration">Collaboration</TabsTrigger>
              <TabsTrigger value="tools">Tools</TabsTrigger>
            </TabsList>
            <TabsContent value="terminal" className="mt-4">
              <CLITerminal liveFeed={state.live_feed} agents={state.agents} />
            </TabsContent>
            <TabsContent value="agents" className="mt-4">
              <AgentTree agents={state.agents} />
            </TabsContent>
            <TabsContent value="collaboration" className="mt-4">
              <CollaborationPanel collaboration={state.collaboration} agents={state.agents} />
            </TabsContent>
            <TabsContent value="tools" className="mt-4">
              <ToolExecutions tools={state.tool_executions} />
            </TabsContent>
          </Tabs>
        </div>
        <div>
          <VulnerabilityPanel vulnerabilities={state.vulnerabilities} />
        </div>
      </div>
    </div>
  )
}