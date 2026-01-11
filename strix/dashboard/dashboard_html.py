"""Modern Dashboard HTML Generator for Strix.

Generates a professional CLI-like developer dashboard using React, shadcn/ui styling,
and modern UI components. This dashboard provides real-time visibility into AI agent
thinking and actions, similar to how developers view CLI-based AI agents like Claude Code.

Key Features:
- CLI Terminal Panel: Real-time stream of AI thinking, reasoning, and tool calls
- Agent Activity Tree: Visual hierarchy of main agent and sub-agents
- Multi-Agent Collaboration: Claims, findings, work queue visualization
- Terminal Output: Command execution results
- Vulnerability Panel: Discovered vulnerabilities with severity breakdown
- Resource Usage: Tokens, cost, rate limiting visualization
- Time Tracking: Progress bar with warnings
"""


def get_dashboard_html() -> str:
    """Generate the complete dashboard HTML with React and modern styling."""
    return '''<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🦉 Strix Security Dashboard</title>
    
    <!-- React -->
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        strix: {
                            green: '#22c55e',
                            dark: '#0f172a',
                            darker: '#0a0f1a',
                            border: 'rgba(34, 197, 94, 0.3)',
                        }
                    },
                    fontFamily: {
                        mono: ['JetBrains Mono', 'SF Mono', 'Monaco', 'Inconsolata', 'monospace'],
                    }
                }
            }
        }
    </script>
    
    <!-- Lucide Icons -->
    <script src="https://unpkg.com/lucide@latest"></script>
    
    <!-- Google Fonts - JetBrains Mono -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
        :root {
            --strix-green: #22c55e;
            --strix-dark: #0f172a;
            --strix-darker: #0a0f1a;
            --strix-border: rgba(34, 197, 94, 0.3);
            --strix-hover: rgba(34, 197, 94, 0.1);
        }
        
        * {
            scrollbar-width: thin;
            scrollbar-color: rgba(34, 197, 94, 0.3) transparent;
        }
        
        *::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        
        *::-webkit-scrollbar-track {
            background: transparent;
        }
        
        *::-webkit-scrollbar-thumb {
            background-color: rgba(34, 197, 94, 0.3);
            border-radius: 3px;
        }
        
        *::-webkit-scrollbar-thumb:hover {
            background-color: rgba(34, 197, 94, 0.5);
        }
        
        body {
            background: linear-gradient(135deg, var(--strix-darker) 0%, var(--strix-dark) 100%);
            font-family: 'JetBrains Mono', monospace;
        }
        
        @keyframes pulse-green {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
        
        @keyframes typing {
            from { width: 0; }
            to { width: 100%; }
        }
        
        @keyframes slide-in {
            from { 
                opacity: 0;
                transform: translateY(-10px);
            }
            to { 
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .animate-pulse-green {
            animation: pulse-green 2s ease-in-out infinite;
        }
        
        .animate-blink {
            animation: blink 1s step-end infinite;
        }
        
        .animate-slide-in {
            animation: slide-in 0.3s ease-out forwards;
        }
        
        .cli-line {
            animation: slide-in 0.2s ease-out forwards;
        }
        
        .panel {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid var(--strix-border);
            border-radius: 8px;
            backdrop-filter: blur(10px);
        }
        
        .panel-header {
            background: rgba(34, 197, 94, 0.1);
            border-bottom: 1px solid var(--strix-border);
            padding: 10px 16px;
            font-weight: 600;
            color: var(--strix-green);
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .cli-terminal {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .cli-line-thinking {
            color: #8b949e;
            font-style: italic;
        }
        
        .cli-line-tool {
            color: #58a6ff;
        }
        
        .cli-line-result {
            color: #3fb950;
        }
        
        .cli-line-error {
            color: #f85149;
        }
        
        .cli-line-user {
            color: #a371f7;
        }
        
        .severity-critical { color: #f85149; font-weight: 600; }
        .severity-high { color: #f97316; }
        .severity-medium { color: #f59e0b; }
        .severity-low { color: #22c55e; }
        .severity-info { color: #3b82f6; }
        
        .status-running { 
            background: #22c55e;
            animation: pulse-green 2s ease-in-out infinite;
        }
        .status-waiting { background: #f59e0b; }
        .status-completed { background: #3b82f6; }
        .status-failed { background: #f85149; }
        .status-stopped { background: #6b7280; }
        
        .tab-button {
            padding: 8px 16px;
            background: transparent;
            border: none;
            color: #8b949e;
            cursor: pointer;
            transition: all 0.2s;
            border-bottom: 2px solid transparent;
            font-size: 13px;
        }
        
        .tab-button:hover {
            color: #ffffff;
            background: rgba(34, 197, 94, 0.05);
        }
        
        .tab-button.active {
            color: var(--strix-green);
            border-bottom-color: var(--strix-green);
        }
        
        .metric-card {
            background: rgba(34, 197, 94, 0.05);
            border: 1px solid var(--strix-border);
            border-radius: 6px;
            padding: 12px;
        }
        
        .progress-bar {
            height: 6px;
            border-radius: 3px;
            background: rgba(34, 197, 94, 0.2);
            overflow: hidden;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
            transition: width 0.5s ease;
        }
        
        .progress-fill.warning {
            background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
        }
        
        .progress-fill.critical {
            background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
        }
        
        .connection-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .connection-indicator.connected {
            background: #22c55e;
            box-shadow: 0 0 8px #22c55e;
        }
        
        .connection-indicator.disconnected {
            background: #f85149;
        }
        
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 2px 8px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 500;
        }
        
        .badge-green { background: rgba(34, 197, 94, 0.2); color: #22c55e; }
        .badge-blue { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #f59e0b; }
        .badge-red { background: rgba(239, 68, 68, 0.2); color: #ef4444; }
        .badge-purple { background: rgba(168, 85, 247, 0.2); color: #a855f7; }
        
        .agent-tree-item {
            padding-left: 16px;
            border-left: 2px solid var(--strix-border);
            margin-left: 8px;
        }
        
        .tooltip {
            position: relative;
        }
        
        .tooltip:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #1f2937;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            white-space: nowrap;
            z-index: 100;
        }
    </style>
</head>
<body class="min-h-screen text-gray-300">
    <div id="root"></div>
    
    <script type="text/babel">
        const { useState, useEffect, useRef, useCallback, useMemo } = React;

        // Icons component using Lucide
        const Icon = ({ name, size = 16, className = "" }) => {
            const ref = useRef(null);
            useEffect(() => {
                if (ref.current && lucide[name]) {
                    ref.current.innerHTML = '';
                    const icon = lucide.createElement(lucide[name]);
                    icon.setAttribute('width', size);
                    icon.setAttribute('height', size);
                    if (className) icon.setAttribute('class', className);
                    ref.current.appendChild(icon);
                }
            }, [name, size, className]);
            return <span ref={ref} className="inline-flex items-center" />;
        };

        // Time formatting utility
        const formatTime = (date) => {
            if (!date) return '--:--:--';
            const d = new Date(date);
            return d.toLocaleTimeString('en-US', { hour12: false });
        };

        const formatDuration = (minutes) => {
            if (minutes < 1) return `${Math.round(minutes * 60)}s`;
            if (minutes < 60) return `${minutes.toFixed(1)}m`;
            return `${Math.floor(minutes / 60)}h ${Math.round(minutes % 60)}m`;
        };

        // Connection Status Component
        const ConnectionStatus = ({ connected }) => (
            <div className={`fixed top-3 right-3 z-50 flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                connected ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 
                           'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
                <span className={`connection-indicator ${connected ? 'connected' : 'disconnected'}`} />
                {connected ? 'Connected' : 'Reconnecting...'}
            </div>
        );

        // Header Component
        const Header = ({ lastUpdate, scanConfig }) => {
            const target = scanConfig?.targets?.[0]?.details?.target_url || 
                          scanConfig?.targets?.[0]?.details?.target_repo ||
                          scanConfig?.targets?.[0]?.original || 'No target';
            
            return (
                <header className="border-b border-strix-border bg-strix-darker/80 backdrop-blur-sm sticky top-0 z-40">
                    <div className="max-w-[1920px] mx-auto px-4 py-3 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="text-2xl">🦉</span>
                            <div>
                                <h1 className="text-lg font-bold text-strix-green flex items-center gap-2">
                                    Strix Security Dashboard
                                    <span className="badge badge-green">Live</span>
                                </h1>
                                <p className="text-xs text-gray-500 truncate max-w-md" title={target}>
                                    Target: {target}
                                </p>
                            </div>
                        </div>
                        <div className="text-xs text-gray-500">
                            Last update: {formatTime(lastUpdate)}
                        </div>
                    </div>
                </header>
            );
        };

        // Time Progress Component
        const TimeProgress = ({ time }) => {
            const progress = time?.progress_percentage || 0;
            const isWarning = time?.is_warning;
            const isCritical = time?.is_critical;
            
            return (
                <div className="panel">
                    <div className="panel-header">
                        <Icon name="Clock" size={14} />
                        <span>Time Remaining</span>
                    </div>
                    <div className="p-4">
                        <div className={`text-xl font-bold mb-2 ${
                            isCritical ? 'text-red-400' : isWarning ? 'text-yellow-400' : 'text-strix-green'
                        }`}>
                            {time?.status || 'Starting...'}
                        </div>
                        <div className="progress-bar mb-3">
                            <div 
                                className={`progress-fill ${isCritical ? 'critical' : isWarning ? 'warning' : ''}`}
                                style={{ width: `${progress}%` }}
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-xs">
                            <div>
                                <span className="text-gray-500">Elapsed</span>
                                <div className="text-white font-medium">
                                    {formatDuration(time?.elapsed_minutes || 0)}
                                </div>
                            </div>
                            <div>
                                <span className="text-gray-500">Remaining</span>
                                <div className="text-white font-medium">
                                    {formatDuration(time?.remaining_minutes || 0)}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            );
        };

        // Current Action Component  
        const CurrentAction = ({ currentStep }) => (
            <div className="panel">
                <div className="panel-header">
                    <Icon name="Play" size={14} />
                    <span>Current Action</span>
                    {currentStep?.status === 'running' && (
                        <span className="ml-auto flex items-center gap-1 text-strix-green">
                            <span className="w-2 h-2 rounded-full bg-strix-green animate-pulse-green" />
                            Running
                        </span>
                    )}
                </div>
                <div className="p-4">
                    <div className="text-base font-semibold text-strix-green mb-1">
                        {currentStep?.agent_name || 'Initializing...'}
                    </div>
                    <div className="text-sm text-gray-400 mb-2 truncate">
                        {currentStep?.action || 'Waiting for agent activity...'}
                    </div>
                    {currentStep?.tool_name && (
                        <div className="flex items-center gap-2 text-xs">
                            <Icon name="Wrench" size={12} className="text-blue-400" />
                            <span className="text-blue-400">{currentStep.tool_name}</span>
                        </div>
                    )}
                </div>
            </div>
        );

        // Resource Usage Component
        const ResourceUsage = ({ resources, rateLimiter }) => (
            <div className="panel">
                <div className="panel-header">
                    <Icon name="BarChart3" size={14} />
                    <span>Resources</span>
                </div>
                <div className="p-4 space-y-4">
                    {/* Rate Limiter Status */}
                    <div className="metric-card">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-xs text-gray-400">Rate Limit (60/min)</span>
                            <span className={`badge ${
                                (rateLimiter?.current_rate || 0) >= 54 ? 'badge-red' :
                                (rateLimiter?.current_rate || 0) >= 42 ? 'badge-yellow' : 'badge-green'
                            }`}>
                                {rateLimiter?.current_rate || 0}/min
                            </span>
                        </div>
                        <div className="progress-bar">
                            <div 
                                className={`progress-fill ${
                                    (rateLimiter?.current_rate || 0) >= 54 ? 'critical' :
                                    (rateLimiter?.current_rate || 0) >= 42 ? 'warning' : ''
                                }`}
                                style={{ width: `${((rateLimiter?.current_rate || 0) / 60) * 100}%` }}
                            />
                        </div>
                    </div>
                    
                    {/* API Calls */}
                    <div className="grid grid-cols-2 gap-3">
                        <div className="metric-card text-center">
                            <div className="text-xl font-bold text-strix-green">
                                {(resources?.api_calls || resources?.request_count || 0).toLocaleString()}
                            </div>
                            <div className="text-xs text-gray-500">API Calls</div>
                        </div>
                        <div className="metric-card text-center">
                            <div className="text-xl font-bold text-blue-400">
                                ${(resources?.total_cost || resources?.cost || 0).toFixed(4)}
                            </div>
                            <div className="text-xs text-gray-500">Cost</div>
                        </div>
                    </div>
                    
                    {/* Tokens */}
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                        <div>
                            <div className="text-sm font-medium text-green-400">
                                {(resources?.input_tokens || 0).toLocaleString()}
                            </div>
                            <div className="text-gray-500">Input</div>
                        </div>
                        <div>
                            <div className="text-sm font-medium text-blue-400">
                                {(resources?.output_tokens || 0).toLocaleString()}
                            </div>
                            <div className="text-gray-500">Output</div>
                        </div>
                        <div>
                            <div className="text-sm font-medium text-yellow-400">
                                {(resources?.cached_tokens || 0).toLocaleString()}
                            </div>
                            <div className="text-gray-500">Cached</div>
                        </div>
                    </div>
                </div>
            </div>
        );

        // CLI Terminal Panel - Shows AI thinking in real-time like Claude Code CLI
        const CLITerminal = ({ liveFeed, agents }) => {
            const terminalRef = useRef(null);
            const [autoScroll, setAutoScroll] = useState(true);
            
            useEffect(() => {
                if (autoScroll && terminalRef.current) {
                    terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
                }
            }, [liveFeed, autoScroll]);
            
            const handleScroll = () => {
                if (terminalRef.current) {
                    const { scrollTop, scrollHeight, clientHeight } = terminalRef.current;
                    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
                }
            };
            
            const getLineStyle = (entry) => {
                switch (entry.type) {
                    case 'thinking': return 'cli-line-thinking';
                    case 'tool_execution': return 'cli-line-tool';
                    case 'tool_result': return 'cli-line-result';
                    case 'error': return 'cli-line-error';
                    case 'user': return 'cli-line-user';
                    case 'chat_message': 
                        return entry.role === 'user' ? 'cli-line-user' : 'cli-line-thinking';
                    default: return '';
                }
            };
            
            const getIcon = (entry) => {
                switch (entry.type) {
                    case 'thinking': return '💭';
                    case 'tool_execution': return '🔧';
                    case 'tool_result': return '✓';
                    case 'error': return '✗';
                    case 'vulnerability': return '🐛';
                    case 'agent_created': return '🤖';
                    case 'chat_message': return entry.role === 'user' ? '👤' : '🤖';
                    default: return '▸';
                }
            };
            
            const formatEntry = (entry) => {
                const time = formatTime(entry.timestamp);
                const icon = getIcon(entry);
                
                switch (entry.type) {
                    case 'thinking':
                        return `${time} ${icon} [Thinking] ${entry.content || '...'}`;
                    case 'tool_execution':
                        const status = entry.status === 'completed' ? '✓' : 
                                      entry.status === 'failed' ? '✗' : '●';
                        return `${time} ${icon} ${entry.tool_name} ${status} ${entry.args_summary || ''}`;
                    case 'tool_result':
                        return `${time} ${icon} [Result] ${entry.content || ''}`;
                    case 'error':
                        return `${time} ${icon} [Error] ${entry.message || entry.content || ''}`;
                    case 'vulnerability':
                        return `${time} ${icon} [VULN] ${entry.severity?.toUpperCase()}: ${entry.title}`;
                    case 'agent_created':
                        return `${time} ${icon} [Agent Created] ${entry.agent_name}`;
                    case 'chat_message':
                        const role = entry.role === 'user' ? 'User' : 'Agent';
                        return `${time} ${icon} [${role}] ${entry.content_preview || ''}`;
                    default:
                        return `${time} ▸ ${JSON.stringify(entry)}`;
                }
            };
            
            return (
                <div className="cli-terminal h-full flex flex-col">
                    <div className="flex items-center justify-between px-3 py-2 bg-[#161b22] border-b border-[#30363d]">
                        <div className="flex items-center gap-2">
                            <div className="flex gap-1.5">
                                <span className="w-3 h-3 rounded-full bg-[#ff5f56]"></span>
                                <span className="w-3 h-3 rounded-full bg-[#ffbd2e]"></span>
                                <span className="w-3 h-3 rounded-full bg-[#27ca41]"></span>
                            </div>
                            <span className="text-xs text-gray-500 ml-2">AI Agent Terminal</span>
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
                            <span className="text-xs text-gray-600">
                                {liveFeed?.length || 0} entries
                            </span>
                        </div>
                    </div>
                    <div 
                        ref={terminalRef}
                        onScroll={handleScroll}
                        className="flex-1 overflow-y-auto p-3 text-xs leading-relaxed"
                        style={{ maxHeight: '400px' }}
                    >
                        {(!liveFeed || liveFeed.length === 0) ? (
                            <div className="text-gray-600 flex items-center gap-2">
                                <span className="animate-pulse">▸</span>
                                Waiting for agent activity...
                                <span className="animate-blink">_</span>
                            </div>
                        ) : (
                            liveFeed.slice(-100).map((entry, idx) => (
                                <div 
                                    key={idx} 
                                    className={`cli-line py-0.5 ${getLineStyle(entry)}`}
                                >
                                    {formatEntry(entry)}
                                </div>
                            ))
                        )}
                        {liveFeed && liveFeed.length > 0 && (
                            <div className="text-gray-600 mt-1">
                                <span className="animate-blink">_</span>
                            </div>
                        )}
                    </div>
                </div>
            );
        };

        // Agent Tree Component
        const AgentTree = ({ agents }) => {
            const agentList = Object.values(agents || {});
            const rootAgents = agentList.filter(a => !a.parent_id);
            
            const getStatusColor = (status) => {
                switch (status) {
                    case 'running': return 'status-running';
                    case 'waiting': return 'status-waiting';
                    case 'completed': return 'status-completed';
                    case 'failed': return 'status-failed';
                    default: return 'status-stopped';
                }
            };
            
            const renderAgent = (agent, depth = 0) => {
                const children = agentList.filter(a => a.parent_id === agent.id);
                
                return (
                    <div key={agent.id} className={depth > 0 ? 'agent-tree-item' : ''}>
                        <div className="flex items-center gap-2 py-2 px-3 rounded hover:bg-white/5">
                            <span className={`w-2 h-2 rounded-full ${getStatusColor(agent.status)}`} />
                            <div className="flex-1 min-w-0">
                                <div className="text-sm font-medium text-white truncate">
                                    {agent.name || 'Agent'}
                                </div>
                                {agent.task && (
                                    <div className="text-xs text-gray-500 truncate">
                                        {agent.task}
                                    </div>
                                )}
                            </div>
                            <span className={`badge ${
                                agent.status === 'running' ? 'badge-green' :
                                agent.status === 'completed' ? 'badge-blue' :
                                agent.status === 'failed' ? 'badge-red' : 'badge-yellow'
                            }`}>
                                {agent.status}
                            </span>
                        </div>
                        {children.length > 0 && (
                            <div className="ml-2">
                                {children.map(child => renderAgent(child, depth + 1))}
                            </div>
                        )}
                    </div>
                );
            };
            
            return (
                <div className="space-y-1">
                    {rootAgents.length === 0 ? (
                        <div className="text-center text-gray-500 py-8 text-sm">
                            No agents running yet...
                        </div>
                    ) : (
                        rootAgents.map(agent => renderAgent(agent))
                    )}
                </div>
            );
        };

        // Tool Executions Component
        const ToolExecutions = ({ tools }) => (
            <div className="space-y-2">
                {(!tools || tools.length === 0) ? (
                    <div className="text-center text-gray-500 py-8 text-sm">
                        No tool executions yet...
                    </div>
                ) : (
                    tools.slice(-50).reverse().map((tool, idx) => {
                        const duration = tool.duration_seconds;
                        const durationStr = duration !== null && duration !== undefined
                            ? (duration < 1 ? `${(duration * 1000).toFixed(0)}ms` : `${duration.toFixed(2)}s`)
                            : '';
                        
                        const hasError = tool.status === 'failed' && tool.error_message;
                        
                        return (
                            <div key={idx} className="rounded bg-white/5 hover:bg-white/10">
                                <div className="flex items-center justify-between p-2">
                                    <div className="flex items-center gap-2 flex-1 min-w-0">
                                        <Icon name="Wrench" size={12} className="text-blue-400 flex-shrink-0" />
                                        <span className="text-sm text-blue-400 font-medium truncate">
                                            {tool.tool_name}
                                        </span>
                                        {durationStr && (
                                            <span className="text-xs text-gray-600">
                                                {durationStr}
                                            </span>
                                        )}
                                        {tool.agent_id && (
                                            <span className="text-xs text-gray-600 truncate">
                                                by {tool.agent_id.slice(0, 8)}
                                            </span>
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className={
                                            tool.status === 'completed' ? 'text-green-400' :
                                            tool.status === 'failed' ? 'text-red-400' : 'text-yellow-400'
                                        }>
                                            {tool.status === 'completed' ? '✓' : 
                                             tool.status === 'failed' ? '✗' : '●'}
                                        </span>
                                    </div>
                                </div>
                                {hasError && (
                                    <div className="px-2 pb-2">
                                        <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
                                            <div className="font-semibold mb-1">Error:</div>
                                            <div className="font-mono text-red-300">
                                                {tool.error_message}
                                            </div>
                                            {tool.error_traceback && (
                                                <details className="mt-2">
                                                    <summary className="cursor-pointer text-red-300 hover:text-red-200">
                                                        Show traceback
                                                    </summary>
                                                    <pre className="mt-1 text-xs overflow-x-auto">
                                                        {tool.error_traceback}
                                                    </pre>
                                                </details>
                                            )}
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })
                )}
            </div>
        );

        // Collaboration Panel Component
        const CollaborationPanel = ({ collaboration }) => {
            const [activeTab, setActiveTab] = useState('claims');
            
            return (
                <div>
                    <div className="flex gap-2 mb-4">
                        {['claims', 'findings', 'queue', 'help'].map(tab => (
                            <button
                                key={tab}
                                onClick={() => setActiveTab(tab)}
                                className={`tab-button ${activeTab === tab ? 'active' : ''}`}
                            >
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                <span className="ml-1 text-xs opacity-60">
                                    ({collaboration?.[tab === 'queue' ? 'work_queue' : tab === 'help' ? 'help_requests' : tab]?.length || 0})
                                </span>
                            </button>
                        ))}
                    </div>
                    
                    <div className="space-y-2 max-h-60 overflow-y-auto">
                        {activeTab === 'claims' && (
                            collaboration?.claims?.length > 0 ? (
                                collaboration.claims.map((claim, idx) => (
                                    <div key={idx} className="p-2 rounded bg-white/5 text-sm">
                                        <span className="text-strix-green">{claim.target}</span>
                                        <span className="text-gray-500 ml-2">[{claim.test_type}]</span>
                                        <span className="text-gray-600 ml-2 text-xs">by {claim.agent_name}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-gray-500 text-center py-4">No active claims</div>
                            )
                        )}
                        
                        {activeTab === 'findings' && (
                            collaboration?.findings?.length > 0 ? (
                                collaboration.findings.map((finding, idx) => (
                                    <div key={idx} className="p-2 rounded bg-white/5 text-sm">
                                        <span className={`severity-${finding.severity?.toLowerCase()}`}>
                                            {finding.title}
                                        </span>
                                        <span className="text-gray-500 ml-2">[{finding.vulnerability_type}]</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-gray-500 text-center py-4">No shared findings</div>
                            )
                        )}
                        
                        {activeTab === 'queue' && (
                            collaboration?.work_queue?.length > 0 ? (
                                collaboration.work_queue.map((item, idx) => (
                                    <div key={idx} className="p-2 rounded bg-white/5 text-sm">
                                        <span className="text-blue-400">{item.target}</span>
                                        <span className="text-gray-500 ml-2">{item.description}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-gray-500 text-center py-4">Work queue empty</div>
                            )
                        )}
                        
                        {activeTab === 'help' && (
                            collaboration?.help_requests?.length > 0 ? (
                                collaboration.help_requests.map((req, idx) => (
                                    <div key={idx} className="p-2 rounded bg-white/5 text-sm">
                                        <span className="text-yellow-400">[{req.help_type}]</span>
                                        <span className="text-gray-300 ml-2">{req.description}</span>
                                    </div>
                                ))
                            ) : (
                                <div className="text-gray-500 text-center py-4">No help requests</div>
                            )
                        )}
                    </div>
                    
                    {/* Stats */}
                    <div className="grid grid-cols-4 gap-2 mt-4 pt-4 border-t border-white/10">
                        <div className="text-center">
                            <div className="text-lg font-bold text-strix-green">
                                {collaboration?.claims?.length || 0}
                            </div>
                            <div className="text-xs text-gray-500">Claims</div>
                        </div>
                        <div className="text-center">
                            <div className="text-lg font-bold text-blue-400">
                                {collaboration?.findings?.length || 0}
                            </div>
                            <div className="text-xs text-gray-500">Findings</div>
                        </div>
                        <div className="text-center">
                            <div className="text-lg font-bold text-purple-400">
                                {collaboration?.work_queue?.length || 0}
                            </div>
                            <div className="text-xs text-gray-500">Queue</div>
                        </div>
                        <div className="text-center">
                            <div className="text-lg font-bold text-yellow-400">
                                {collaboration?.help_requests?.length || 0}
                            </div>
                            <div className="text-xs text-gray-500">Help</div>
                        </div>
                    </div>
                </div>
            );
        };

        // Vulnerability Panel Component
        const VulnerabilityPanel = ({ vulnerabilities }) => {
            const counts = useMemo(() => {
                const c = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
                vulnerabilities?.forEach(v => {
                    const sev = (v.severity || 'info').toLowerCase();
                    if (c[sev] !== undefined) c[sev]++;
                });
                return c;
            }, [vulnerabilities]);
            
            return (
                <div className="panel h-full">
                    <div className="panel-header justify-between">
                        <div className="flex items-center gap-2">
                            <Icon name="Bug" size={14} />
                            <span>Vulnerabilities</span>
                        </div>
                        <span className="bg-gray-700 px-2 py-0.5 rounded text-xs">
                            {vulnerabilities?.length || 0}
                        </span>
                    </div>
                    <div className="p-4">
                        {/* Severity Breakdown */}
                        <div className="grid grid-cols-5 gap-2 mb-4 text-center">
                            <div>
                                <div className="text-lg font-bold severity-critical">{counts.critical}</div>
                                <div className="text-xs text-gray-500">Critical</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold severity-high">{counts.high}</div>
                                <div className="text-xs text-gray-500">High</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold severity-medium">{counts.medium}</div>
                                <div className="text-xs text-gray-500">Medium</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold severity-low">{counts.low}</div>
                                <div className="text-xs text-gray-500">Low</div>
                            </div>
                            <div>
                                <div className="text-lg font-bold severity-info">{counts.info}</div>
                                <div className="text-xs text-gray-500">Info</div>
                            </div>
                        </div>
                        
                        {/* Vulnerability List */}
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                            {(!vulnerabilities || vulnerabilities.length === 0) ? (
                                <div className="text-center text-gray-500 py-4 text-sm">
                                    No vulnerabilities discovered yet
                                </div>
                            ) : (
                                vulnerabilities.slice(0, 20).map((vuln, idx) => (
                                    <div key={idx} className="p-2 rounded bg-white/5 hover:bg-white/10">
                                        <div className="flex items-center justify-between">
                                            <span className={`text-sm font-medium severity-${(vuln.severity || 'info').toLowerCase()}`}>
                                                {vuln.title || 'Vulnerability'}
                                            </span>
                                            <span className={`badge badge-${
                                                vuln.severity === 'critical' ? 'red' :
                                                vuln.severity === 'high' ? 'yellow' :
                                                vuln.severity === 'medium' ? 'yellow' : 'blue'
                                            }`}>
                                                {vuln.severity || 'info'}
                                            </span>
                                        </div>
                                        {vuln.target && (
                                            <div className="text-xs text-gray-500 mt-1 truncate">
                                                {vuln.target}
                                            </div>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                    </div>
                </div>
            );
        };

        // Main Tabbed Content Area
        const MainContent = ({ state }) => {
            const [activeTab, setActiveTab] = useState('terminal');
            
            return (
                <div className="panel flex-1">
                    <div className="flex border-b border-white/10">
                        {[
                            { id: 'terminal', icon: 'Terminal', label: 'AI Terminal' },
                            { id: 'agents', icon: 'Users', label: 'Agents' },
                            { id: 'collaboration', icon: 'GitBranch', label: 'Collaboration' },
                            { id: 'tools', icon: 'Wrench', label: 'Tools' },
                        ].map(tab => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`tab-button flex items-center gap-2 ${activeTab === tab.id ? 'active' : ''}`}
                            >
                                <Icon name={tab.icon} size={14} />
                                {tab.label}
                            </button>
                        ))}
                    </div>
                    
                    <div className="p-4" style={{ minHeight: '400px' }}>
                        {activeTab === 'terminal' && (
                            <CLITerminal liveFeed={state.live_feed} agents={state.agents} />
                        )}
                        {activeTab === 'agents' && (
                            <AgentTree agents={state.agents} />
                        )}
                        {activeTab === 'collaboration' && (
                            <CollaborationPanel collaboration={state.collaboration} />
                        )}
                        {activeTab === 'tools' && (
                            <ToolExecutions tools={state.tool_executions} />
                        )}
                    </div>
                </div>
            );
        };

        // Main Dashboard App
        const Dashboard = () => {
            const [state, setState] = useState({
                scan_config: {},
                agents: {},
                tool_executions: [],
                chat_messages: [],
                vulnerabilities: [],
                collaboration: {
                    claims: [],
                    findings: [],
                    work_queue: [],
                    help_requests: [],
                    messages: [],
                    stats: {},
                },
                resources: {},
                rate_limiter: {},
                time: {},
                current_step: {},
                live_feed: [],
                last_updated: null,
            });
            const [connected, setConnected] = useState(false);
            
            useEffect(() => {
                let eventSource = null;
                let reconnectTimer = null;
                
                const connect = () => {
                    eventSource = new EventSource('/api/stream');
                    
                    eventSource.onopen = () => {
                        setConnected(true);
                        console.log('SSE connected');
                    };
                    
                    eventSource.addEventListener('state', (e) => {
                        try {
                            const data = JSON.parse(e.data);
                            setState(prev => ({ ...prev, ...data }));
                        } catch (err) {
                            console.error('Failed to parse state:', err);
                        }
                    });
                    
                    eventSource.addEventListener('update', (e) => {
                        try {
                            const data = JSON.parse(e.data);
                            setState(prev => ({ ...prev, ...data }));
                        } catch (err) {
                            console.error('Failed to parse update:', err);
                        }
                    });
                    
                    eventSource.onerror = () => {
                        setConnected(false);
                        eventSource.close();
                        reconnectTimer = setTimeout(connect, 3000);
                    };
                };
                
                connect();
                
                // Also fetch initial state via REST
                fetch('/api/state')
                    .then(r => r.json())
                    .then(data => setState(prev => ({ ...prev, ...data })))
                    .catch(console.error);
                
                return () => {
                    if (eventSource) eventSource.close();
                    if (reconnectTimer) clearTimeout(reconnectTimer);
                };
            }, []);
            
            return (
                <div className="min-h-screen">
                    <ConnectionStatus connected={connected} />
                    <Header lastUpdate={state.last_updated} scanConfig={state.scan_config} />
                    
                    <main className="max-w-[1920px] mx-auto p-4">
                        {/* Top Row - Stats */}
                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
                            <TimeProgress time={state.time} />
                            <CurrentAction currentStep={state.current_step} />
                            <ResourceUsage resources={state.resources} rateLimiter={state.rate_limiter} />
                        </div>
                        
                        {/* Main Content Row */}
                        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                            <div className="xl:col-span-2">
                                <MainContent state={state} />
                            </div>
                            <div>
                                <VulnerabilityPanel vulnerabilities={state.vulnerabilities} />
                            </div>
                        </div>
                    </main>
                    
                    {/* Footer */}
                    <footer className="border-t border-white/10 mt-8 py-4 text-center text-xs text-gray-600">
                        <p>
                            🦉 Strix Security Scanner | 
                            <a href="https://usestrix.com" className="text-strix-green hover:underline ml-1">Website</a> |
                            <a href="https://discord.gg/YjKFvEZSdZ" className="text-strix-green hover:underline ml-1">Discord</a>
                        </p>
                        <p className="mt-1">This dashboard provides real-time monitoring of AI agent activity</p>
                    </footer>
                </div>
            );
        };
        
        // Render the app
        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(<Dashboard />);
    </script>
</body>
</html>'''


def get_dashboard_css() -> str:
    """Return empty string - CSS is embedded in HTML."""
    return ""


def get_dashboard_js() -> str:
    """Return empty string - JS is embedded in HTML."""
    return ""
