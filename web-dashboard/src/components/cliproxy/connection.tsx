'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI } from '@/lib/cliproxy-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import {
  Server,
  Key,
  CheckCircle,
  XCircle,
  Loader2,
  Eye,
  EyeOff,
  Copy,
  ExternalLink,
  Wifi,
  WifiOff,
  Zap,
  Globe,
  Terminal,
} from 'lucide-react';

export function CLIProxyConnection() {
  const { 
    cliProxyConfig, 
    setCLIProxyConfig, 
    cliProxyConnected, 
    setCLIProxyConnected,
    settings,
    updateSettings,
  } = useStrixStore();
  
  const [localBaseUrl, setLocalBaseUrl] = useState(cliProxyConfig.baseUrl);
  const [localManagementKey, setLocalManagementKey] = useState(cliProxyConfig.managementKey);
  const [showKey, setShowKey] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);

  // Test connection
  const testConnection = async () => {
    setTesting(true);
    setTestResult(null);

    try {
      cliProxyAPI.setBaseUrl(localBaseUrl);
      cliProxyAPI.setManagementKey(localManagementKey);
      
      const isConnected = await cliProxyAPI.checkHealth();
      setCLIProxyConnected(isConnected);

      if (isConnected) {
        setTestResult({ success: true, message: 'Successfully connected to CLIProxyAPI!' });
        // Save configuration
        setCLIProxyConfig({
          baseUrl: localBaseUrl,
          managementKey: localManagementKey,
        });
        // Fetch available models
        fetchModels();
      } else {
        setTestResult({ success: false, message: 'Failed to connect. Check your URL and management key.' });
      }
    } catch (error) {
      setTestResult({ success: false, message: `Connection error: ${error}` });
      setCLIProxyConnected(false);
    } finally {
      setTesting(false);
    }
  };

  // Fetch available models
  const fetchModels = async () => {
    setLoadingModels(true);
    try {
      const models = await cliProxyAPI.getAvailableModels();
      setAvailableModels(models);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    } finally {
      setLoadingModels(false);
    }
  };

  // Enable CLIProxy as default provider
  const enableAsDefaultProvider = () => {
    updateSettings({
      llmProvider: 'cliproxy',
      apiBase: `${localBaseUrl}/v1`,
      apiKey: localManagementKey || 'cliproxy-default',
    });
    setCLIProxyConfig({ enabled: true });
  };

  // Copy API endpoint
  const copyEndpoint = (endpoint: string) => {
    navigator.clipboard.writeText(`${localBaseUrl}${endpoint}`);
  };

  useEffect(() => {
    if (cliProxyConnected) {
      fetchModels();
    }
  }, [cliProxyConnected]);

  return (
    <div className="space-y-6">
      {/* Connection Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            Connection Settings
          </CardTitle>
          <CardDescription>
            Configure your CLIProxyAPI server connection
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Server URL</label>
            <div className="flex gap-2">
              <Input
                value={localBaseUrl}
                onChange={(e) => setLocalBaseUrl(e.target.value)}
                placeholder="http://localhost:8317"
                className="flex-1"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              The base URL of your CLIProxyAPI server (default: http://localhost:8317)
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Management Key (Optional)</label>
            <div className="relative">
              <Input
                type={showKey ? 'text' : 'password'}
                value={localManagementKey}
                onChange={(e) => setLocalManagementKey(e.target.value)}
                placeholder="Enter management key..."
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              Required for management API access. Set in your CLIProxyAPI config.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <Button onClick={testConnection} disabled={testing}>
              {testing ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Testing...
                </>
              ) : (
                <>
                  <Wifi className="mr-2 h-4 w-4" />
                  Test Connection
                </>
              )}
            </Button>

            <div className="flex items-center gap-2">
              <Switch
                checked={cliProxyConfig.enabled}
                onCheckedChange={(enabled) => setCLIProxyConfig({ enabled })}
              />
              <span className="text-sm">Enable CLIProxyAPI</span>
            </div>
          </div>

          {testResult && (
            <Alert variant={testResult.success ? 'default' : 'destructive'}>
              {testResult.success ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              <AlertTitle>{testResult.success ? 'Success' : 'Error'}</AlertTitle>
              <AlertDescription>{testResult.message}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* API Endpoints */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            API Endpoints
          </CardTitle>
          <CardDescription>
            Available endpoints for your AI applications
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3">
            {[
              { name: 'Chat Completions', path: '/v1/chat/completions', description: 'OpenAI-compatible chat API' },
              { name: 'Models', path: '/v1/models', description: 'List available models' },
              { name: 'Embeddings', path: '/v1/embeddings', description: 'Generate embeddings' },
              { name: 'Responses', path: '/v1/responses', description: 'OpenAI Responses API' },
              { name: 'Management', path: '/v0/management', description: 'Management API (requires key)' },
            ].map((endpoint) => (
              <div
                key={endpoint.path}
                className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
              >
                <div>
                  <p className="font-medium">{endpoint.name}</p>
                  <p className="text-xs text-muted-foreground">{endpoint.description}</p>
                </div>
                <div className="flex items-center gap-2">
                  <code className="text-xs bg-background px-2 py-1 rounded">
                    {localBaseUrl}{endpoint.path}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => copyEndpoint(endpoint.path)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Default Provider Setup */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            Use as Default Provider
          </CardTitle>
          <CardDescription>
            Set CLIProxyAPI as the default LLM provider for Strix
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Terminal className="h-4 w-4" />
            <AlertTitle>One-Click Setup</AlertTitle>
            <AlertDescription>
              Enable CLIProxyAPI as your default provider to use all your connected accounts
              (Google, Claude, OpenAI, etc.) with automatic load balancing and failover.
            </AlertDescription>
          </Alert>

          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-600 flex items-center justify-center">
                <Zap className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-medium">CLIProxyAPI Provider</p>
                <p className="text-sm text-muted-foreground">
                  Current: {settings.llmProvider === 'cliproxy' ? 'Enabled' : 'Disabled'}
                </p>
              </div>
            </div>
            <Button
              onClick={enableAsDefaultProvider}
              disabled={!cliProxyConnected}
              variant={settings.llmProvider === 'cliproxy' ? 'secondary' : 'default'}
            >
              {settings.llmProvider === 'cliproxy' ? (
                <>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Active
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  Enable
                </>
              )}
            </Button>
          </div>

          {settings.llmProvider === 'cliproxy' && (
            <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg">
              <p className="text-sm text-green-600 dark:text-green-400">
                CLIProxyAPI is now your default provider. All AI requests will be routed through it.
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Available Models */}
      {cliProxyConnected && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5" />
              Available Models
              <Badge variant="secondary">{availableModels.length}</Badge>
            </CardTitle>
            <CardDescription>
              Models available through CLIProxyAPI from all connected providers
            </CardDescription>
          </CardHeader>
          <CardContent>
            {loadingModels ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : availableModels.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {availableModels.map((model) => (
                  <Badge key={model} variant="outline" className="font-mono text-xs">
                    {model}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No models available. Add accounts or API keys to enable models.
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Quick Start Guide */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Terminal className="h-5 w-5" />
            Quick Start
          </CardTitle>
          <CardDescription>
            Get started with CLIProxyAPI in 3 simple steps
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <div className="flex gap-3">
              <div className="flex-shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                1
              </div>
              <div>
                <p className="font-medium">Install CLIProxyAPI</p>
                <code className="text-xs bg-muted px-2 py-1 rounded block mt-1">
                  # Download from GitHub releases or use Docker
                </code>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                2
              </div>
              <div>
                <p className="font-medium">Start the proxy server</p>
                <code className="text-xs bg-muted px-2 py-1 rounded block mt-1">
                  cliproxy run --port 8317
                </code>
              </div>
            </div>
            <div className="flex gap-3">
              <div className="flex-shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                3
              </div>
              <div>
                <p className="font-medium">Login with your accounts</p>
                <p className="text-sm text-muted-foreground">
                  Use the Accounts tab to add Google, Claude, OpenAI accounts via OAuth
                </p>
              </div>
            </div>
          </div>

          <Button
            variant="outline"
            className="w-full"
            onClick={() => window.open('https://help.router-for.me/', '_blank')}
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            View Full Documentation
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
