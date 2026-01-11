'use client'

import { useMemo, useRef, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Network } from 'lucide-react'
import type { Collaboration, Agent } from '@/types'

interface CollaborationNetworkGraphProps {
  collaboration: Collaboration | undefined
  agents: Record<string, Agent> | undefined
}

interface Node {
  id: string
  label: string
  type: 'agent' | 'finding' | 'claim' | 'work'
  x?: number
  y?: number
  fx?: number
  fy?: number
}

interface Link {
  source: string
  target: string
  type: string
  weight?: number
}

export function CollaborationNetworkGraph({
  collaboration,
  agents,
}: CollaborationNetworkGraphProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const { nodes, links } = useMemo(() => {
    const nodeMap = new Map<string, Node>()
    const linkList: Link[] = []

    // Add agent nodes
    if (agents) {
      Object.values(agents).forEach((agent) => {
        nodeMap.set(agent.id, {
          id: agent.id,
          label: agent.name || agent.id.slice(0, 8),
          type: 'agent',
        })
      })
    }

    // Add finding nodes and links to agents
    if (collaboration?.findings) {
      collaboration.findings.forEach((finding) => {
        const findingId = `finding-${finding.finding_id}`
        nodeMap.set(findingId, {
          id: findingId,
          label: finding.title?.slice(0, 20) || finding.finding_id,
          type: 'finding',
        })

        if (finding.found_by && agents) {
          Object.values(agents).forEach((agent) => {
            if (agent.name === finding.found_by || agent.id.includes(finding.found_by || '')) {
              linkList.push({
                source: agent.id,
                target: findingId,
                type: 'found',
                weight: 1,
              })
            }
          })
        }
      })
    }

    // Add claim nodes and links
    if (collaboration?.claims) {
      collaboration.claims.forEach((claim) => {
        const claimId = `claim-${claim.target}-${claim.test_type}`
        if (!nodeMap.has(claimId)) {
          nodeMap.set(claimId, {
            id: claimId,
            label: `${claim.target.slice(0, 15)}...`,
            type: 'claim',
          })
        }

        if (claim.agent_id && nodeMap.has(claim.agent_id)) {
          linkList.push({
            source: claim.agent_id,
            target: claimId,
            type: 'claims',
            weight: 1,
          })
        }
      })
    }

    // Add work queue items
    if (collaboration?.work_queue) {
      collaboration.work_queue.forEach((work) => {
        const workId = `work-${work.work_id}`
        nodeMap.set(workId, {
          id: workId,
          label: work.target?.slice(0, 15) || work.work_id,
          type: 'work',
        })
      })
    }

    // Link agents that share findings (collaboration)
    if (collaboration?.findings && agents) {
      const findingsByAgent = new Map<string, string[]>()
      collaboration.findings.forEach((finding) => {
        const agentName = finding.found_by || ''
        if (agentName) {
          if (!findingsByAgent.has(agentName)) {
            findingsByAgent.set(agentName, [])
          }
          findingsByAgent.get(agentName)?.push(finding.finding_id)
        }
      })

      // Create links between agents that share similar findings
      const agentList = Object.values(agents)
      for (let i = 0; i < agentList.length; i++) {
        for (let j = i + 1; j < agentList.length; j++) {
          const agent1 = agentList[i]
          const agent2 = agentList[j]
          const findings1 = findingsByAgent.get(agent1.name || '') || []
          const findings2 = findingsByAgent.get(agent2.name || '') || []

          // If they both have findings, create a collaboration link
          if (findings1.length > 0 && findings2.length > 0) {
            linkList.push({
              source: agent1.id,
              target: agent2.id,
              type: 'collaborates',
              weight: Math.min(findings1.length, findings2.length),
            })
          }
        }
      }
    }

    return {
      nodes: Array.from(nodeMap.values()),
      links: linkList,
    }
  }, [collaboration, agents])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Set canvas dimensions
    const rect = canvas.getBoundingClientRect()
    const width = canvas.width = rect.width || 800
    const height = canvas.height = Math.max(400, nodes.length * 30 || 400)

    // Clear canvas
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)'
    ctx.fillRect(0, 0, width, height)

    if (nodes.length === 0) {
      ctx.fillStyle = '#9CA3AF'
      ctx.font = '14px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('No collaboration data available', width / 2, height / 2)
      return
    }

    // Simple force-directed layout
    const centerX = width / 2
    const centerY = height / 2
    const radius = Math.min(width, height) / 3

    // Position nodes in a circle, then apply force simulation
    nodes.forEach((node, i) => {
      if (node.x === undefined || node.y === undefined) {
        const angle = (i * 2 * Math.PI) / nodes.length
        node.x = centerX + radius * Math.cos(angle)
        node.y = centerY + radius * Math.sin(angle)
      }
    })

    // Simple force simulation
    for (let iteration = 0; iteration < 50; iteration++) {
      nodes.forEach((node) => {
        let fx = 0
        let fy = 0

        // Repulsion from other nodes
        nodes.forEach((other) => {
          if (node.id === other.id) return
          const dx = (node.x || 0) - (other.x || 0)
          const dy = (node.y || 0) - (other.y || 0)
          const distance = Math.sqrt(dx * dx + dy * dy) || 1
          const force = 1000 / (distance * distance)
          fx += (dx / distance) * force
          fy += (dy / distance) * force
        })

        // Attraction from links
        links.forEach((link) => {
          const target = link.source === node.id ? link.target : link.source === node.id ? link.source : null
          if (!target) return
          const targetNode = nodes.find((n) => n.id === target)
          if (!targetNode || !targetNode.x || !targetNode.y) return

          const dx = (targetNode.x || 0) - (node.x || 0)
          const dy = (targetNode.y || 0) - (node.y || 0)
          const distance = Math.sqrt(dx * dx + dy * dy) || 1
          const force = distance * 0.01
          fx += (dx / distance) * force
          fy += (dy / distance) * force
        })

        // Apply forces with damping
        if (node.x !== undefined && node.y !== undefined) {
          node.x += fx * 0.1
          node.y += fy * 0.1

          // Keep nodes within bounds
          node.x = Math.max(20, Math.min(width - 20, node.x))
          node.y = Math.max(20, Math.min(height - 20, node.y))
        }
      })
    }

    // Draw links
    links.forEach((link) => {
      const sourceNode = nodes.find((n) => n.id === link.source)
      const targetNode = nodes.find((n) => n.id === link.target)

      if (!sourceNode || !targetNode || !sourceNode.x || !sourceNode.y || !targetNode.x || !targetNode.y) {
        return
      }

      ctx.strokeStyle =
        link.type === 'found'
          ? 'rgba(239, 68, 68, 0.5)'
          : link.type === 'claims'
            ? 'rgba(59, 130, 246, 0.5)'
            : 'rgba(34, 197, 94, 0.5)'
      ctx.lineWidth = link.weight || 1
      ctx.beginPath()
      ctx.moveTo(sourceNode.x, sourceNode.y)
      ctx.lineTo(targetNode.x, targetNode.y)
      ctx.stroke()
    })

    // Draw nodes
    nodes.forEach((node) => {
      if (!node.x || !node.y) return

      const colors = {
        agent: { fill: '#22C55E', stroke: '#16A34A' },
        finding: { fill: '#EF4444', stroke: '#DC2626' },
        claim: { fill: '#3B82F6', stroke: '#2563EB' },
        work: { fill: '#F59E0B', stroke: '#D97706' },
      }

      const color = colors[node.type] || colors.agent

      // Draw node circle
      ctx.fillStyle = color.fill
      ctx.strokeStyle = color.stroke
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.arc(node.x, node.y, 12, 0, 2 * Math.PI)
      ctx.fill()
      ctx.stroke()

      // Draw label
      ctx.fillStyle = '#E5E7EB'
      ctx.font = '11px monospace'
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(node.label, node.x, node.y + 16)
    })

    // Draw legend
    ctx.fillStyle = 'rgba(15, 23, 42, 0.9)'
    ctx.fillRect(10, 10, 200, 100)
    ctx.strokeStyle = '#374151'
    ctx.strokeRect(10, 10, 200, 100)

    ctx.font = '12px monospace'
    ctx.fillStyle = '#E5E7EB'
    ctx.textAlign = 'left'
    ctx.fillText('Legend:', 20, 30)
    ctx.fillStyle = '#22C55E'
    ctx.fillRect(20, 40, 12, 12)
    ctx.fillStyle = '#E5E7EB'
    ctx.fillText('Agent', 38, 42)
    ctx.fillStyle = '#EF4444'
    ctx.fillRect(20, 58, 12, 12)
    ctx.fillStyle = '#E5E7EB'
    ctx.fillText('Finding', 38, 60)
    ctx.fillStyle = '#3B82F6'
    ctx.fillRect(20, 76, 12, 12)
    ctx.fillStyle = '#E5E7EB'
    ctx.fillText('Claim', 38, 78)
    ctx.fillStyle = '#F59E0B'
    ctx.fillRect(120, 40, 12, 12)
    ctx.fillStyle = '#E5E7EB'
    ctx.fillText('Work', 138, 42)
  }, [nodes, links])

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm flex items-center gap-2">
          <Network className="h-4 w-4" />
          Collaboration Network
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="w-full overflow-auto">
          <canvas
            ref={canvasRef}
            className="w-full border border-border rounded-md"
            style={{ minHeight: '400px' }}
          />
        </div>
        <div className="mt-4 text-xs text-muted-foreground grid grid-cols-2 gap-2">
          <div>Nodes: {nodes.length}</div>
          <div>Links: {links.length}</div>
        </div>
      </CardContent>
    </Card>
  )
}