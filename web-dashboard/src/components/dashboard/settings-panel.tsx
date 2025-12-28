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
} from 'lucide-react';

const LLM_PROVIDERS = [
  { value: 'openai', label: 'OpenAI', models: ['gpt-4', 'gpt-4-turbo', 'gpt-4o', 'gpt-3.5-turbo'] },
  { value: 'anthropic', label: 'Anthropic', models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'] },
  { value: 'google', label: 'Google', models: ['gemini-pro', 'gemini-ultra'] },
  { value: 'local', label: 'Local/Custom', models: ['custom'] },
];

export function SettingsPanel() {
  const { settings, updateSettings, serverUrl, setServerUrl, connected } = useStrixStore();
  const [showApiKey, setShowApiKey] = useState(false);
  const [showPerplexityKey, setShowPerplexityKey] = useState(false);
  const [localServerUrl, setLocalServerUrl] = useState(serverUrl);
  const [saved, setSaved] = useState(false);

  const currentProvider = LLM_PROVIDERS.find((p) => p.value === settings.llmProvider);
  const availableModels = currentProvider?.models || [];

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
                onValueChange={(v) => updateSettings({ llmProvider: v })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LLM_PROVIDERS.map((provider) => (
                    <SelectItem key={provider.value} value={provider.value}>
                      {provider.label}
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

          <div className="space-y-2">
            <label className="text-sm font-medium">Custom API Base (Optional)</label>
            <Input
              value={settings.apiBase}
              onChange={(e) => updateSettings({ apiBase: e.target.value })}
              placeholder="https://api.openai.com/v1"
            />
            <p className="text-xs text-muted-foreground">
              For local models (Ollama, LMStudio) or custom endpoints
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
