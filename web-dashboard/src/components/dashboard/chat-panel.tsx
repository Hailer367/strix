'use client';

import { useState, useRef, useEffect, useMemo } from 'react';
import { useStrixStore } from '@/lib/store';
import { useStrixWebSocket } from '@/lib/websocket';
import { cn } from '@/lib/utils';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  MessageSquare,
  Send,
  Bot,
  User,
  Terminal,
  Globe,
  Code,
  FileEdit,
  Search,
  Brain,
  Loader2,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

interface ChatMessageProps {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  const isUser = role === 'user';

  return (
    <div
      className={cn(
        'flex gap-3 p-3 rounded-lg',
        isUser ? 'bg-primary/10' : 'bg-muted/50'
      )}
    >
      <div
        className={cn(
          'flex items-center justify-center h-8 w-8 rounded-full shrink-0',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-green-600 text-white'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm">
            {isUser ? 'You' : 'Strix Agent'}
          </span>
          <span className="text-xs text-muted-foreground">
            {formatDistanceToNow(new Date(timestamp), { addSuffix: true })}
          </span>
        </div>
        <div className="text-sm whitespace-pre-wrap break-words">{content}</div>
      </div>
    </div>
  );
}

const TOOL_ICONS: Record<string, typeof Terminal> = {
  terminal_execute: Terminal,
  browser_action: Globe,
  python_action: Code,
  file_edit_action: FileEdit,
  web_search_action: Search,
  thinking_action: Brain,
};

interface ToolExecutionCardProps {
  toolName: string;
  args: Record<string, unknown>;
  status: 'running' | 'completed' | 'failed';
  result: unknown;
  timestamp: string;
}

function ToolExecutionCard({
  toolName,
  args,
  status,
  result,
  timestamp,
}: ToolExecutionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const Icon = TOOL_ICONS[toolName] || Terminal;

  const statusIcon = useMemo(() => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-3 w-3 animate-spin text-yellow-500" />;
      case 'completed':
        return <CheckCircle2 className="h-3 w-3 text-green-500" />;
      case 'failed':
        return <XCircle className="h-3 w-3 text-red-500" />;
    }
  }, [status]);

  const displayName = toolName
    .replace(/_/g, ' ')
    .replace(/action$/i, '')
    .trim();

  return (
    <Card className="bg-muted/30 border-muted">
      <CardHeader
        className="py-2 px-3 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          {expanded ? (
            <ChevronDown className="h-3 w-3" />
          ) : (
            <ChevronRight className="h-3 w-3" />
          )}
          <Icon className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-xs font-medium capitalize flex-1">
            {displayName}
          </CardTitle>
          {statusIcon}
          <span className="text-xs text-muted-foreground">
            {formatDistanceToNow(new Date(timestamp), { addSuffix: true })}
          </span>
        </div>
      </CardHeader>

      {expanded && (
        <CardContent className="py-2 px-3 pt-0">
          <div className="space-y-2">
            {Object.keys(args).length > 0 && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">
                  Args:
                </span>
                <pre className="text-xs bg-background/50 p-2 rounded mt-1 overflow-x-auto">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
            )}
            {result !== null && result !== undefined && (
              <div>
                <span className="text-xs font-medium text-muted-foreground">
                  Result:
                </span>
                <pre className="text-xs bg-background/50 p-2 rounded mt-1 overflow-x-auto max-h-40">
                  {typeof result === 'string'
                    ? (result as string).slice(0, 500)
                    : JSON.stringify(result, null, 2).slice(0, 500)}
                  {(typeof result === 'string' ? (result as string) : JSON.stringify(result)).length > 500 && '...'}
                </pre>
              </div>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

export function ChatPanel() {
  const [message, setMessage] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const {
    selectedAgentId,
    agents,
    chatMessages,
    toolExecutions,
    settings,
  } = useStrixStore();
  const { sendUserMessage } = useStrixWebSocket();

  const selectedAgent = selectedAgentId ? agents[selectedAgentId] : null;

  // Filter messages and tools for selected agent
  const agentMessages = useMemo(() => {
    if (!selectedAgentId) return [];
    return chatMessages.filter((m) => m.agentId === selectedAgentId);
  }, [chatMessages, selectedAgentId]);

  const agentTools = useMemo(() => {
    if (!selectedAgentId) return [];
    return Object.values(toolExecutions)
      .filter((t) => t.agentId === selectedAgentId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  }, [toolExecutions, selectedAgentId]);

  // Combine and sort events
  const events = useMemo(() => {
    const allEvents: Array<{
      type: 'message' | 'tool';
      timestamp: string;
      data: (typeof agentMessages)[0] | (typeof agentTools)[0];
    }> = [
      ...agentMessages.map((m) => ({ type: 'message' as const, timestamp: m.timestamp, data: m })),
      ...agentTools.map((t) => ({ type: 'tool' as const, timestamp: t.timestamp, data: t })),
    ];
    return allEvents.sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [agentMessages, agentTools]);

  // Auto-scroll
  useEffect(() => {
    if (settings.autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events, settings.autoScroll]);

  const handleSend = () => {
    if (!message.trim() || !selectedAgentId) return;
    sendUserMessage(selectedAgentId, message.trim());
    setMessage('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!selectedAgent) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground p-4">
        <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
        <p className="text-sm text-center">Select an agent to view activity</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-600 text-white">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-medium text-sm">{selectedAgent.name}</h3>
            <p className="text-xs text-muted-foreground">
              Iteration {selectedAgent.iteration}/{selectedAgent.maxIterations}
            </p>
          </div>
        </div>
        <Badge
          variant={
            selectedAgent.status === 'running'
              ? 'default'
              : selectedAgent.status === 'completed'
              ? 'secondary'
              : 'destructive'
          }
          className="capitalize"
        >
          {selectedAgent.status}
        </Badge>
      </div>

      {/* Messages */}
      <ScrollArea className="flex-1" ref={scrollRef}>
        <div className="p-4 space-y-3">
          {events.length === 0 ? (
            <div className="text-center text-muted-foreground text-sm py-8">
              Agent activity will appear here...
            </div>
          ) : (
            events.map((event, idx) => {
              if (event.type === 'message') {
                const msg = event.data as (typeof agentMessages)[0];
                return (
                  <ChatMessage
                    key={`msg-${idx}`}
                    role={msg.role}
                    content={msg.content}
                    timestamp={msg.timestamp}
                  />
                );
              } else {
                const tool = event.data as (typeof agentTools)[0];
                return (
                  <ToolExecutionCard
                    key={`tool-${idx}`}
                    toolName={tool.toolName}
                    args={tool.args}
                    status={tool.status}
                    result={tool.result}
                    timestamp={tool.timestamp}
                  />
                );
              }
            })
          )}
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t p-3 bg-muted/30">
        <div className="flex gap-2">
          <Textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Message ${selectedAgent.name}...`}
            className="min-h-[60px] max-h-[120px] resize-none"
            disabled={selectedAgent.status !== 'running' && selectedAgent.status !== 'waiting'}
          />
          <Button
            onClick={handleSend}
            disabled={
              !message.trim() ||
              (selectedAgent.status !== 'running' && selectedAgent.status !== 'waiting')
            }
            size="icon"
            className="h-[60px] w-[60px]"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
