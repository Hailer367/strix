'use client';

import { useState } from 'react';
import { useStrixStore } from '@/lib/store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import {
  Settings,
  Key,
  Server,
  Palette,
  Bell,
  Bot,
  Save,
  Eye,
  EyeOff,
  CheckCircle2,
  Network,
  Zap,
  ExternalLink,
} from 'lucide-react';

const LLM_PROVIDERS = [
  { 
    value: 'cliproxy', 
    label: 'CLIProxyAPI (Recommended)', 
    models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'claude-sonnet-4', 'claude-3-5-sonnet', 'gpt-4o', 'gpt-5', 'o3', 'o1'],
    description: 'Unified API gateway - Use your Google/Claude/OpenAI accounts',
    recommended: true,
  },
  { value: 'openai', label: 'OpenAI (Direct)', models: ['gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-3.5-turbo', 'gpt-5', 'o1', 'o3'] },
  { value: 'anthropic', label: 'Anthropic (Direct)', models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku', 'claude-sonnet-4'] },
  { value: 'google', label: 'Google (Direct)', models: ['gemini-pro', 'gemini-ultra', 'gemini-2.5-pro', 'gemini-2.5-flash'] },
  { value: 'local', label: 'Local/Custom', models: ['custom'] },
];

export function SettingsPanel() {
  const { settings, updateSettings, serverUrl, setServerUrl, connected, cliProxyConnected, cliProxyConfig, setActivePanel } = useStrixStore();
  const [showApiKey, setShowApiKey] = useState(false);
  const [showPerplexityKey, setShowPerplexityKey] = useState(false);
  const [localServerUrl, setLocalServerUrl] = useState(serverUrl);
  const [saved, setSaved] = useState(false);

  const currentProvider = LLM_PROVIDERS.find((p) => p.value === settings.llmProvider);
  const availableModels = currentProvider?.models || [];
  const isCLIProxy = settings.llmProvider === 'cliproxy';

  const handleSave = () => {
    // Save server URL if changed
    if (localServerUrl !== serverUrl) {
      setServerUrl(localServerUrl);
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="p-6 space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center gap-3">
        <Settings className="h-6 w-6 text-muted-foreground" />
        <div>
          <h2 className="text-xl font-semibold">Settings</h2>
          <p className="text-sm text-muted-foreground">
            Configure your Strix dashboard and scanning preferences
          </p>
        </div>
      </div>

      <Separator />

      {/* Server Connection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            Server Connection
          </CardTitle>
          <CardDescription>
            Connect to your Strix backend server
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Server URL</label>
            <div className="flex gap-2">
              <Input
                value={localServerUrl}
                onChange={(e) => setLocalServerUrl(e.target.value)}
                placeholder="ws://localhost:8000/ws"
              />
              <div className="flex items-center gap-2">
                <div
                  className={`h-3 w-3 rounded-full ${
                    connected ? 'bg-green-500' : 'bg-red-500'
                  }`}
                />
                <span className="text-sm text-muted-foreground">
                  {connected ? 'Connected' : 'Disconnected'}
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* CLIProxyAPI Quick Setup */}
      <Card className="border-purple-500/50 bg-gradient-to-br from-purple-500/5 to-blue-500/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5 text-purple-500" />
            CLIProxyAPI - Recommended
            {cliProxyConnected && (
              <span className="h-2 w-2 rounded-full bg-green-500" />
            )}
          </CardTitle>
          <CardDescription>
            Use your Google/Claude/OpenAI subscriptions with automatic load balancing
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Zap className="h-4 w-4" />
            <AlertTitle>No API Keys Needed!</AlertTitle>
            <AlertDescription>
              CLIProxyAPI lets you use your existing Google, Claude, and OpenAI accounts via OAuth.
              All models from connected accounts are available with automatic failover.
            </AlertDescription>
          </Alert>

          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                <Network className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-medium">CLIProxyAPI Status</p>
                <p className="text-sm text-muted-foreground">
                  {cliProxyConnected ? 'Connected' : 'Not Connected'}
                  {cliProxyConnected && ` - ${cliProxyConfig.baseUrl}`}
                </p>
              </div>
            </div>
            <Button
              variant={isCLIProxy ? 'secondary' : 'default'}
              onClick={() => setActivePanel('cliproxy')}
            >
              <ExternalLink className="mr-2 h-4 w-4" />
              {isCLIProxy ? 'Manage' : 'Setup'}
            </Button>
          </div>

          {!cliProxyConnected && (
            <p className="text-xs text-muted-foreground">
              Click "Setup" to configure CLIProxyAPI as your AI provider.
            </p>
          )}
        </CardContent>
      </Card>

      {/* LLM Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bot className="h-5 w-5" />
            LLM Configuration
          </CardTitle>
          <CardDescription>
            Configure the language model for AI agents
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Provider</label>
              <Select
                value={settings.llmProvider}
                onValueChange={(v) => {
                  updateSettings({ llmProvider: v });
                  // Auto-set API base for CLIProxy
                  if (v === 'cliproxy') {
                    updateSettings({ apiBase: `${cliProxyConfig.baseUrl}/v1` });
                  }
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LLM_PROVIDERS.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      <div className="flex items-center gap-2">
                        {provider.value === 'cliproxy' && <Network className="h-4 w-4 text-purple-500" />}
                        {provider.label}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Model</label>
              <Select
                value={settings.llmModel}
                onValueChange={(v) => updateSettings({ llmModel: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {isCLIProxy ? (
            <Alert className="bg-purple-500/10 border-purple-500/20">
              <Network className="h-4 w-4" />
              <AlertTitle>CLIProxyAPI Active</AlertTitle>
              <AlertDescription>
                API Key is not required when using CLIProxyAPI. Your connected accounts will be used automatically.
              </AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-2">
              <label className="text-sm font-medium">API Key</label>
              <div className="relative">
                <Input
                  type={showApiKey ? 'text' : 'password'}
                  value={settings.apiKey}
                  onChange={(e) => updateSettings({ apiKey: e.target.value })}
                  placeholder="sk-..."
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowApiKey(!showApiKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showApiKey ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium">API Base URL</label>
            <Input
              value={settings.apiBase}
              onChange={(e) => updateSettings({ apiBase: e.target.value })}
              placeholder={isCLIProxy ? 'http://localhost:8317/v1' : 'https://api.openai.com/v1'}
            />
            <p className="text-xs text-muted-foreground">
              {isCLIProxy 
                ? 'CLIProxyAPI endpoint (auto-configured)'
                : 'For local models (Ollama, LMStudio) or custom endpoints'}
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Max Iterations</label>
            <Input
              type="number"
              value={settings.maxIterations}
              onChange={(e) =>
                updateSettings({ maxIterations: parseInt(e.target.value) || 300 })
              }
              min={10}
              max={1000}
            />
            <p className="text-xs text-muted-foreground">
              Maximum iterations per agent (10-1000)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Key className="h-5 w-5" />
            Additional API Keys
          </CardTitle>
          <CardDescription>
            Optional API keys for enhanced features
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Perplexity API Key</label>
            <div className="relative">
              <Input
                type={showPerplexityKey ? 'text' : 'password'}
                value={settings.perplexityApiKey}
                onChange={(e) => updateSettings({ perplexityApiKey: e.target.value })}
                placeholder="pplx-..."
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPerplexityKey(!showPerplexityKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPerplexityKey ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Enables real-time web search for agents
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Appearance
          </CardTitle>
          <CardDescription>Customize the dashboard appearance</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Theme</label>
            <Select
              value={settings.theme}
              onValueChange={(v) =>
                updateSettings({ theme: v as 'light' | 'dark' | 'system' })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
                <SelectItem value="system">System</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Auto-scroll Messages</p>
              <p className="text-xs text-muted-foreground">
                Automatically scroll to new messages
              </p>
            </div>
            <Switch
              checked={settings.autoScroll}
              onCheckedChange={(v) => updateSettings({ autoScroll: v })}
            />
          </div>
        </CardContent>
      </Card>

      {/* Notifications */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notifications
          </CardTitle>
          <CardDescription>Configure notification preferences</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Sound Notifications</p>
              <p className="text-xs text-muted-foreground">
                Play sound when vulnerabilities are found
              </p>
            </div>
            <Switch
              checked={settings.soundNotifications}
              onCheckedChange={(v) => updateSettings({ soundNotifications: v })}
            />
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div className="flex justify-end">
        <Button onClick={handleSave} className="min-w-[120px]">
          {saved ? (
            <>
              <CheckCircle2 className="h-4 w-4 mr-2" />
              Saved!
            </>
          ) : (
            <>
              <Save className="h-4 w-4 mr-2" />
              Save Settings
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
