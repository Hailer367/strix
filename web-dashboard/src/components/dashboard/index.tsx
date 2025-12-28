'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { useStrixWebSocket } from '@/lib/websocket';
import { cn } from '@/lib/utils';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { AgentTree } from './agent-tree';
import { ChatPanel } from './chat-panel';
import { VulnerabilityPanel } from './vulnerability-panel';
import { ScanControl } from './scan-control';
import { SettingsPanel } from './settings-panel';
import { StatsPanel } from './stats-panel';
import {
  Bot,
  Bug,
  Terminal,
  Settings,
  Shield,
  Menu,
  X,
  Wifi,
  WifiOff,
  Moon,
  Sun,
  Github,
  HelpCircle,
  Network,
} from 'lucide-react';
import { CLIProxyDashboard } from '@/components/cliproxy';

export function StrixDashboard() {
  const {
    connected,
    sidebarOpen,
    toggleSidebar,
    activePanel,
    setActivePanel,
    vulnerabilities,
    settings,
    updateSettings,
    cliProxyConnected,
  } = useStrixStore();
  const { } = useStrixWebSocket();

  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const toggleTheme = () => {
    const newTheme = settings.theme === 'dark' ? 'light' : 'dark';
    updateSettings({ theme: newTheme });
  };

  if (!mounted) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <div className="flex items-center gap-3">
          <Shield className="h-8 w-8 text-green-500 animate-pulse" />
          <span className="text-xl font-semibold">Loading Strix...</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('min-h-screen bg-background', settings.theme === 'dark' && 'dark')}>
      {/* Top Navigation Bar - Cockpit Header */}
      <header className="h-14 border-b bg-card/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="flex items-center justify-between h-full px-4">
          {/* Left Section - Logo & Menu */}
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleSidebar}
              className="lg:hidden"
            >
              {sidebarOpen ? (
                <X className="h-5 w-5" />
              ) : (
                <Menu className="h-5 w-5" />
              )}
            </Button>

            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center h-9 w-9 rounded-lg bg-green-600">
                <Shield className="h-5 w-5 text-white" />
              </div>
              <div>
                <h1 className="font-bold text-lg leading-none">Strix</h1>
                <p className="text-xs text-muted-foreground leading-none mt-0.5">
                  Security Dashboard
                </p>
              </div>
            </div>
          </div>

          {/* Center Section - Connection Status */}
          <div className="hidden md:flex items-center gap-4">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-muted">
                    {connected ? (
                      <>
                        <Wifi className="h-4 w-4 text-green-500" />
                        <span className="text-sm text-green-500">Connected</span>
                      </>
                    ) : (
                      <>
                        <WifiOff className="h-4 w-4 text-red-500" />
                        <span className="text-sm text-red-500">Disconnected</span>
                      </>
                    )}
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  {connected
                    ? 'Connected to Strix server'
                    : 'Not connected - configure server URL in settings'}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Right Section - Actions */}
          <div className="flex items-center gap-2">
            {vulnerabilities.length > 0 && (
              <Badge variant="destructive" className="hidden sm:flex">
                <Bug className="h-3 w-3 mr-1" />
                {vulnerabilities.length} vuln{vulnerabilities.length !== 1 ? 's' : ''}
              </Badge>
            )}

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" onClick={toggleTheme}>
                    {settings.theme === 'dark' ? (
                      <Sun className="h-5 w-5" />
                    ) : (
                      <Moon className="h-5 w-5" />
                    )}
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Toggle theme</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() =>
                      window.open('https://github.com/usestrix/strix', '_blank')
                    }
                  >
                    <Github className="h-5 w-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>View on GitHub</TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon">
                    <HelpCircle className="h-5 w-5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Help & Documentation</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="flex h-[calc(100vh-3.5rem)]">
        {/* Left Sidebar - Panel Tabs */}
        <aside
          className={cn(
            'w-14 border-r bg-card/30 flex flex-col items-center py-4 gap-2',
            'transition-all duration-300',
            !sidebarOpen && 'hidden lg:flex'
          )}
        >
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={activePanel === 'agents' ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={() => setActivePanel('agents')}
                  className="relative"
                >
                  <Bot className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Agents</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={activePanel === 'vulnerabilities' ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={() => setActivePanel('vulnerabilities')}
                  className="relative"
                >
                  <Bug className="h-5 w-5" />
                  {vulnerabilities.length > 0 && (
                    <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-red-500 text-[10px] text-white flex items-center justify-center">
                      {vulnerabilities.length > 9 ? '9+' : vulnerabilities.length}
                    </span>
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Vulnerabilities</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={activePanel === 'terminal' ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={() => setActivePanel('terminal')}
                >
                  <Terminal className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Terminal Output</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={activePanel === 'cliproxy' ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={() => setActivePanel('cliproxy')}
                  className="relative"
                >
                  <Network className="h-5 w-5" />
                  {cliProxyConnected && (
                    <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-green-500" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">CLIProxyAPI</TooltipContent>
            </Tooltip>

            <div className="flex-1" />

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant={activePanel === 'settings' ? 'secondary' : 'ghost'}
                  size="icon"
                  onClick={() => setActivePanel('settings')}
                >
                  <Settings className="h-5 w-5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Settings</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </aside>

        {/* Main Panel Area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {activePanel === 'settings' ? (
            <div className="overflow-auto">
              <SettingsPanel />
            </div>
          ) : activePanel === 'cliproxy' ? (
            <div className="overflow-auto">
              <CLIProxyDashboard />
            </div>
          ) : (
            <>
              {/* Scan Control */}
              <div className="p-3 border-b">
                <ScanControl />
              </div>

              {/* Stats */}
              <StatsPanel />

              {/* Resizable Panels */}
              <div className="flex-1 overflow-hidden">
                <ResizablePanelGroup direction="horizontal" className="h-full">
                  {/* Left Panel - Agent Tree or Vulnerabilities */}
                  <ResizablePanel defaultSize={30} minSize={20} maxSize={50}>
                    <div className="h-full border-r">
                      {activePanel === 'agents' && <AgentTree />}
                      {activePanel === 'vulnerabilities' && <VulnerabilityPanel />}
                      {activePanel === 'terminal' && (
                        <div className="p-4 h-full flex flex-col">
                          <h3 className="font-medium mb-4 flex items-center gap-2">
                            <Terminal className="h-4 w-4" />
                            Terminal Output
                          </h3>
                          <div className="flex-1 bg-black rounded-lg p-4 font-mono text-sm text-green-400 overflow-auto">
                            <pre>$ strix --target example.com</pre>
                            <pre className="text-muted-foreground">
                              {/* Terminal output will be populated here */}
                              Terminal output will appear here...
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  </ResizablePanel>

                  <ResizableHandle withHandle />

                  {/* Right Panel - Chat/Activity */}
                  <ResizablePanel defaultSize={70}>
                    <ChatPanel />
                  </ResizablePanel>
                </ResizablePanelGroup>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
