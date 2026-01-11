'use client'

import { useEffect, useRef, useState } from 'react'
import { Card } from '@/components/ui/card'
import { formatTime } from '@/lib/utils'
import type { LiveFeedEntry, Agent } from '@/types'

interface CLITerminalProps {
  liveFeed: LiveFeedEntry[] | undefined
  agents: Record<string, Agent> | undefined
}

export function CLITerminal({ liveFeed, agents }: CLITerminalProps) {
  const terminalRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight
    }
  }, [liveFeed, autoScroll])

  const handleScroll = () => {
    if (terminalRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = terminalRef.current
      setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
    }
  }

  const getLineStyle = (entry: LiveFeedEntry) => {
    switch (entry.type) {
      case 'thinking':
        return 'text-gray-400 italic'
      case 'tool_execution':
        return 'text-blue-400'
      case 'tool_result':
        return 'text-green-400'
      case 'error':
        return 'text-red-400'
      case 'vulnerability':
        return 'text-red-500 font-semibold'
      case 'chat_message':
        return entry.role === 'user' ? 'text-purple-400' : 'text-gray-400'
      default:
        return 'text-gray-300'
    }
  }

  const getIcon = (entry: LiveFeedEntry) => {
    switch (entry.type) {
      case 'thinking':
        return '💭'
      case 'tool_execution':
        return '🔧'
      case 'tool_result':
        return '✓'
      case 'error':
        return '✗'
      case 'vulnerability':
        return '🐛'
      case 'agent_created':
        return '🤖'
      case 'chat_message':
        return entry.role === 'user' ? '👤' : '🤖'
      default:
        return '▸'
    }
  }

  const formatEntry = (entry: LiveFeedEntry) => {
    const time = formatTime(entry.timestamp)
    const icon = getIcon(entry)

    switch (entry.type) {
      case 'thinking':
        return `${time} ${icon} [Thinking] ${entry.content || '...'}`
      case 'tool_execution':
        const status =
          entry.status === 'completed' ? '✓' : entry.status === 'failed' ? '✗' : '●'
        return `${time} ${icon} ${entry.tool_name} ${status} ${entry.args_summary || ''}`
      case 'tool_result':
        return `${time} ${icon} [Result] ${entry.content || ''}`
      case 'error':
        return `${time} ${icon} [Error] ${entry.message || entry.content || ''}`
      case 'vulnerability':
        return `${time} ${icon} [VULN] ${entry.severity?.toUpperCase()}: ${entry.title}`
      case 'agent_created':
        return `${time} ${icon} [Agent Created] ${entry.agent_name}`
      case 'chat_message':
        const role = entry.role === 'user' ? 'User' : 'Agent'
        return `${time} ${icon} [${role}] ${entry.content_preview || ''}`
      default:
        return `${time} ▸ ${JSON.stringify(entry)}`
    }
  }

  return (
    <Card className="h-full flex flex-col bg-[#0d1117] border-[#30363d]">
      <div className="flex items-center justify-between px-3 py-2 bg-[#161b22] border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5">
            <span className="w-3 h-3 rounded-full bg-[#ff5f56]"></span>
            <span className="w-3 h-3 rounded-full bg-[#ffbd2e]"></span>
            <span className="w-3 h-3 rounded-full bg-[#27ca41]"></span>
          </div>
          <span className="text-xs text-muted-foreground ml-2">AI Agent Terminal</span>
        </div>
        <div className="flex items-center gap-2">
          {!autoScroll && (
            <button
              onClick={() => setAutoScroll(true)}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              ↓ Auto-scroll
            </button>
          )}
          <span className="text-xs text-muted-foreground">
            {liveFeed?.length || 0} entries
          </span>
        </div>
      </div>
      <div
        ref={terminalRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto p-3 text-xs leading-relaxed font-mono"
        style={{ maxHeight: '400px' }}
      >
        {!liveFeed || liveFeed.length === 0 ? (
          <div className="text-muted-foreground flex items-center gap-2">
            <span className="animate-pulse">▸</span>
            Waiting for agent activity...
            <span className="animate-pulse">_</span>
          </div>
        ) : (
          <>
            {liveFeed.slice(-100).map((entry, idx) => (
              <div key={idx} className={`py-0.5 ${getLineStyle(entry)} animate-in`}>
                {formatEntry(entry)}
              </div>
            ))}
            <div className="text-muted-foreground mt-1">
              <span className="animate-pulse">_</span>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}