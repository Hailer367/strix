'use client';

import { useMemo } from 'react';
import { useStrixStore, Agent } from '@/lib/store';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Bot,
  ChevronRight,
  Circle,
  CirclePause,
  CheckCircle2,
  XCircle,
  StopCircle,
  AlertCircle,
  Loader2,
} from 'lucide-react';

interface AgentNodeProps {
  agent: Agent;
  children: Agent[];
  depth: number;
  allAgents: Record<string, Agent>;
}

function getStatusIcon(status: Agent['status']) {
  switch (status) {
    case 'running':
      return <Loader2 className="h-3 w-3 animate-spin text-green-500" />;
    case 'waiting':
      return <CirclePause className="h-3 w-3 text-yellow-500" />;
    case 'completed':
      return <CheckCircle2 className="h-3 w-3 text-green-500" />;
    case 'failed':
      return <XCircle className="h-3 w-3 text-red-500" />;
    case 'stopped':
      return <StopCircle className="h-3 w-3 text-gray-500" />;
    case 'llm_failed':
      return <AlertCircle className="h-3 w-3 text-red-500" />;
    default:
      return <Circle className="h-3 w-3 text-gray-400" />;
  }
}

function getStatusColor(status: Agent['status']) {
  switch (status) {
    case 'running':
      return 'border-green-500/50 bg-green-500/10';
    case 'waiting':
      return 'border-yellow-500/50 bg-yellow-500/10';
    case 'completed':
      return 'border-green-600/50 bg-green-600/10';
    case 'failed':
    case 'llm_failed':
      return 'border-red-500/50 bg-red-500/10';
    case 'stopped':
      return 'border-gray-500/50 bg-gray-500/10';
    default:
      return 'border-gray-400/50 bg-gray-400/10';
  }
}

function AgentNode({ agent, children, depth, allAgents }: AgentNodeProps) {
  const { selectedAgentId, selectAgent } = useStrixStore();
  const isSelected = selectedAgentId === agent.id;
  const hasChildren = children.length > 0;

  const childNodes = useMemo(() => {
    return children.map((child) => {
      const grandChildren = Object.values(allAgents).filter(
        (a) => a.parentId === child.id
      );
      return (
        <AgentNode
          key={child.id}
          agent={child}
          children={grandChildren}
          depth={depth + 1}
          allAgents={allAgents}
        />
      );
    });
  }, [children, allAgents, depth]);

  return (
    <Collapsible defaultOpen={true}>
      <div
        className={cn(
          'flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer transition-all',
          'hover:bg-accent/50',
          isSelected && 'bg-accent ring-1 ring-primary/50',
          getStatusColor(agent.status)
        )}
        style={{ marginLeft: `${depth * 16}px` }}
        onClick={() => selectAgent(agent.id)}
      >
        {hasChildren ? (
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-4 w-4 p-0"
              onClick={(e) => e.stopPropagation()}
            >
              <ChevronRight className="h-3 w-3 transition-transform data-[state=open]:rotate-90" />
            </Button>
          </CollapsibleTrigger>
        ) : (
          <div className="w-4" />
        )}

        {getStatusIcon(agent.status)}

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{agent.name}</div>
                <div className="text-xs text-muted-foreground truncate">
                  {agent.task.slice(0, 50)}
                  {agent.task.length > 50 && '...'}
                </div>
              </div>
            </TooltipTrigger>
            <TooltipContent side="right" className="max-w-xs">
              <p className="font-medium">{agent.name}</p>
              <p className="text-xs text-muted-foreground mt-1">{agent.task}</p>
              <div className="flex gap-2 mt-2">
                <Badge variant="outline" className="text-xs">
                  {agent.iteration}/{agent.maxIterations}
                </Badge>
                <Badge variant="outline" className="text-xs capitalize">
                  {agent.status}
                </Badge>
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <Badge variant="secondary" className="text-xs shrink-0">
          {agent.iteration}
        </Badge>
      </div>

      {hasChildren && (
        <CollapsibleContent>{childNodes}</CollapsibleContent>
      )}
    </Collapsible>
  );
}

export function AgentTree() {
  const { agents } = useStrixStore();

  const rootAgents = useMemo(() => {
    return Object.values(agents).filter((agent) => agent.parentId === null);
  }, [agents]);

  const agentCount = Object.keys(agents).length;
  const activeCount = Object.values(agents).filter(
    (a) => a.status === 'running' || a.status === 'waiting'
  ).length;

  if (agentCount === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4">
        <Bot className="h-12 w-12 mb-4 opacity-50" />
        <p className="text-sm text-center">No active agents</p>
        <p className="text-xs text-center mt-1">
          Start a scan to deploy agents
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4" />
          <span className="font-medium text-sm">Agents</span>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="text-xs">
            {activeCount} active
          </Badge>
          <Badge variant="secondary" className="text-xs">
            {agentCount} total
          </Badge>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-2">
          {rootAgents.map((agent) => {
            const children = Object.values(agents).filter(
              (a) => a.parentId === agent.id
            );
            return (
              <AgentNode
                key={agent.id}
                agent={agent}
                children={children}
                depth={0}
                allAgents={agents}
              />
            );
          })}
        </div>
      </ScrollArea>
    </div>
  );
}
