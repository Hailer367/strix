'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI } from '@/lib/cliproxy-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Settings2,
  Save,
  RefreshCw,
  Loader2,
  CheckCircle,
  XCircle,
  Bug,
  Network,
  FileText,
  Shield,
  Trash2,
  Download,
  Eye,
  AlertTriangle,
  RotateCcw,
} from 'lucide-react';

export function CLIProxySettings() {
  const { cliProxyConnected, cliProxyConfig, setCLIProxyConfig } = useStrixStore();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Settings state
  const [debug, setDebug] = useState(false);
  const [requestLog, setRequestLog] = useState(false);
  const [requestRetry, setRequestRetry] = useState(3);
  const [maxRetryInterval, setMaxRetryInterval] = useState(30);
  const [loggingToFile, setLoggingToFile] = useState(false);
  const [usageStatisticsEnabled, setUsageStatisticsEnabled] = useState(true);
  const [wsAuth, setWsAuth] = useState(false);
  const [proxyUrl, setProxyUrl] = useState('');
  const [switchProject, setSwitchProject] = useState(true);
  const [switchPreviewModel, setSwitchPreviewModel] = useState(true);

  // Logs state
  const [logs, setLogs] = useState<string[]>([]);
  const [logsDialogOpen, setLogsDialogOpen] = useState(false);
  const [loadingLogs, setLoadingLogs] = useState(false);

  // Config YAML state
  const [configYaml, setConfigYaml] = useState('');
  const [configDialogOpen, setConfigDialogOpen] = useState(false);

  // Fetch current settings
  const fetchSettings = async () => {
    if (!cliProxyConnected) return;
    
    setLoading(true);
    try {
      const [
        debugRes,
        requestLogRes,
        requestRetryRes,
        maxRetryRes,
        loggingRes,
        usageRes,
        wsAuthRes,
        proxyUrlRes,
        quotaProjectRes,
        quotaPreviewRes,
      ] = await Promise.all([
        cliProxyAPI.getDebug().catch(() => ({ debug: false })),
        cliProxyAPI.getRequestLog().catch(() => ({ 'request-log': false })),
        cliProxyAPI.getRequestRetry().catch(() => ({ 'request-retry': 3 })),
        cliProxyAPI.getMaxRetryInterval().catch(() => ({ 'max-retry-interval': 30 })),
        cliProxyAPI.getLoggingToFile().catch(() => ({ 'logging-to-file': false })),
        cliProxyAPI.getUsageStatisticsEnabled().catch(() => ({ 'usage-statistics-enabled': true })),
        cliProxyAPI.getWsAuth().catch(() => ({ 'ws-auth': false })),
        cliProxyAPI.getProxyUrl().catch(() => ({ 'proxy-url': '' })),
        cliProxyAPI.getQuotaExceededSwitchProject().catch(() => ({ 'switch-project': true })),
        cliProxyAPI.getQuotaExceededSwitchPreviewModel().catch(() => ({ 'switch-preview-model': true })),
      ]);

      setDebug(debugRes.debug);
      setRequestLog(requestLogRes['request-log']);
      setRequestRetry(requestRetryRes['request-retry']);
      setMaxRetryInterval(maxRetryRes['max-retry-interval']);
      setLoggingToFile(loggingRes['logging-to-file']);
      setUsageStatisticsEnabled(usageRes['usage-statistics-enabled']);
      setWsAuth(wsAuthRes['ws-auth']);
      setProxyUrl(proxyUrlRes['proxy-url'] || '');
      setSwitchProject(quotaProjectRes['switch-project']);
      setSwitchPreviewModel(quotaPreviewRes['switch-preview-model']);
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, [cliProxyConnected]);

  // Save individual setting
  const saveSetting = async (setting: string, value: boolean | number | string) => {
    setSaving(true);
    try {
      switch (setting) {
        case 'debug':
          await cliProxyAPI.setDebug(value as boolean);
          break;
        case 'request-log':
          await cliProxyAPI.setRequestLog(value as boolean);
          break;
        case 'request-retry':
          await cliProxyAPI.setRequestRetry(value as number);
          break;
        case 'max-retry-interval':
          await cliProxyAPI.setMaxRetryInterval(value as number);
          break;
        case 'logging-to-file':
          await cliProxyAPI.setLoggingToFile(value as boolean);
          break;
        case 'usage-statistics-enabled':
          await cliProxyAPI.setUsageStatisticsEnabled(value as boolean);
          break;
        case 'ws-auth':
          await cliProxyAPI.setWsAuth(value as boolean);
          break;
        case 'proxy-url':
          if (value) {
            await cliProxyAPI.setProxyUrl(value as string);
          } else {
            await cliProxyAPI.deleteProxyUrl();
          }
          break;
        case 'switch-project':
          await cliProxyAPI.setQuotaExceededSwitchProject(value as boolean);
          break;
        case 'switch-preview-model':
          await cliProxyAPI.setQuotaExceededSwitchPreviewModel(value as boolean);
          break;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (error) {
      console.error('Failed to save setting:', error);
    } finally {
      setSaving(false);
    }
  };

  // Fetch logs
  const fetchLogs = async () => {
    setLoadingLogs(true);
    try {
      const logsRes = await cliProxyAPI.getLogs();
      setLogs(logsRes.lines || []);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoadingLogs(false);
    }
  };

  // Clear logs
  const clearLogs = async () => {
    try {
      await cliProxyAPI.clearLogs();
      setLogs([]);
    } catch (error) {
      console.error('Failed to clear logs:', error);
    }
  };

  // Fetch config YAML
  const fetchConfigYaml = async () => {
    try {
      const yaml = await cliProxyAPI.getConfigYAML();
      setConfigYaml(yaml);
    } catch (error) {
      console.error('Failed to fetch config:', error);
    }
  };

  // Save config YAML
  const saveConfigYaml = async () => {
    try {
      await cliProxyAPI.setConfigYAML(configYaml);
      setConfigDialogOpen(false);
      fetchSettings();
    } catch (error) {
      console.error('Failed to save config:', error);
    }
  };

  if (!cliProxyConnected) {
    return (
      <Alert>
        <XCircle className="h-4 w-4" />
        <AlertTitle>Not Connected</AlertTitle>
        <AlertDescription>
          Please connect to CLIProxyAPI first to manage settings.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Proxy Settings</h3>
          <p className="text-sm text-muted-foreground">
            Configure CLIProxyAPI behavior and features
          </p>
        </div>
        <div className="flex items-center gap-2">
          {saved && (
            <Badge variant="default" className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3" />
              Saved
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={fetchSettings} disabled={loading}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Debug & Logging */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bug className="h-5 w-5" />
            Debug & Logging
          </CardTitle>
          <CardDescription>
            Configure debugging and logging options
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Debug Mode</p>
              <p className="text-xs text-muted-foreground">
                Enable verbose logging for troubleshooting
              </p>
            </div>
            <Switch
              checked={debug}
              onCheckedChange={(checked) => {
                setDebug(checked);
                saveSetting('debug', checked);
              }}
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Request Logging</p>
              <p className="text-xs text-muted-foreground">
                Log all API requests and responses
              </p>
            </div>
            <Switch
              checked={requestLog}
              onCheckedChange={(checked) => {
                setRequestLog(checked);
                saveSetting('request-log', checked);
              }}
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Log to File</p>
              <p className="text-xs text-muted-foreground">
                Persist logs to disk for later analysis
              </p>
            </div>
            <Switch
              checked={loggingToFile}
              onCheckedChange={(checked) => {
                setLoggingToFile(checked);
                saveSetting('logging-to-file', checked);
              }}
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Usage Statistics</p>
              <p className="text-xs text-muted-foreground">
                Collect usage statistics for analytics
              </p>
            </div>
            <Switch
              checked={usageStatisticsEnabled}
              onCheckedChange={(checked) => {
                setUsageStatisticsEnabled(checked);
                saveSetting('usage-statistics-enabled', checked);
              }}
              disabled={saving}
            />
          </div>

          <div className="flex gap-2 pt-2">
            <Dialog open={logsDialogOpen} onOpenChange={setLogsDialogOpen}>
              <DialogTrigger asChild>
                <Button
                  variant="outline"
                  onClick={() => {
                    setLogsDialogOpen(true);
                    fetchLogs();
                  }}
                >
                  <Eye className="h-4 w-4 mr-2" />
                  View Logs
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-4xl max-h-[80vh]">
                <DialogHeader>
                  <DialogTitle>Server Logs</DialogTitle>
                  <DialogDescription>
                    Recent log entries from CLIProxyAPI
                  </DialogDescription>
                </DialogHeader>
                <ScrollArea className="h-[400px] border rounded-md p-4 bg-black">
                  {loadingLogs ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="h-6 w-6 animate-spin" />
                    </div>
                  ) : logs.length > 0 ? (
                    <pre className="text-xs text-green-400 font-mono">
                      {logs.join('\n')}
                    </pre>
                  ) : (
                    <p className="text-muted-foreground text-center">No logs available</p>
                  )}
                </ScrollArea>
                <DialogFooter>
                  <Button variant="outline" onClick={fetchLogs} disabled={loadingLogs}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Refresh
                  </Button>
                  <Button variant="destructive" onClick={clearLogs}>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Clear Logs
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardContent>
      </Card>

      {/* Request Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            Request Settings
          </CardTitle>
          <CardDescription>
            Configure request retry and proxy behavior
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Request Retry Count</label>
              <Input
                type="number"
                value={requestRetry}
                onChange={(e) => setRequestRetry(parseInt(e.target.value) || 0)}
                onBlur={() => saveSetting('request-retry', requestRetry)}
                min={0}
                max={10}
              />
              <p className="text-xs text-muted-foreground">
                Number of retry attempts on failure (0-10)
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Max Retry Interval (seconds)</label>
              <Input
                type="number"
                value={maxRetryInterval}
                onChange={(e) => setMaxRetryInterval(parseInt(e.target.value) || 0)}
                onBlur={() => saveSetting('max-retry-interval', maxRetryInterval)}
                min={1}
                max={300}
              />
              <p className="text-xs text-muted-foreground">
                Maximum time between retries (1-300s)
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Proxy URL (Optional)</label>
            <Input
              value={proxyUrl}
              onChange={(e) => setProxyUrl(e.target.value)}
              onBlur={() => saveSetting('proxy-url', proxyUrl)}
              placeholder="socks5://proxy.example.com:1080"
            />
            <p className="text-xs text-muted-foreground">
              Route all requests through this proxy (supports http, https, socks5)
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Security Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Security
          </CardTitle>
          <CardDescription>
            Configure security and authentication options
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">WebSocket Authentication</p>
              <p className="text-xs text-muted-foreground">
                Require authentication for WebSocket connections
              </p>
            </div>
            <Switch
              checked={wsAuth}
              onCheckedChange={(checked) => {
                setWsAuth(checked);
                saveSetting('ws-auth', checked);
              }}
              disabled={saving}
            />
          </div>

          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Warning</AlertTitle>
            <AlertDescription>
              Enabling WebSocket authentication will disconnect all current sessions.
              They will need to reconnect with valid credentials.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Quota Exceeded Behavior */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RotateCcw className="h-5 w-5" />
            Quota Exceeded Behavior
          </CardTitle>
          <CardDescription>
            What to do when rate limits or quotas are hit
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Switch Project</p>
              <p className="text-xs text-muted-foreground">
                Automatically switch to another account when quota exceeded
              </p>
            </div>
            <Switch
              checked={switchProject}
              onCheckedChange={(checked) => {
                setSwitchProject(checked);
                saveSetting('switch-project', checked);
              }}
              disabled={saving}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">Switch to Preview Model</p>
              <p className="text-xs text-muted-foreground">
                Fall back to preview/experimental model if available
              </p>
            </div>
            <Switch
              checked={switchPreviewModel}
              onCheckedChange={(checked) => {
                setSwitchPreviewModel(checked);
                saveSetting('switch-preview-model', checked);
              }}
              disabled={saving}
            />
          </div>
        </CardContent>
      </Card>

      {/* Raw Config */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Configuration File
          </CardTitle>
          <CardDescription>
            View and edit the raw YAML configuration
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Dialog open={configDialogOpen} onOpenChange={setConfigDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="outline"
                onClick={() => {
                  setConfigDialogOpen(true);
                  fetchConfigYaml();
                }}
              >
                <FileText className="h-4 w-4 mr-2" />
                Edit Config YAML
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl max-h-[80vh]">
              <DialogHeader>
                <DialogTitle>Configuration File</DialogTitle>
                <DialogDescription>
                  Edit the raw YAML configuration. Changes take effect immediately.
                </DialogDescription>
              </DialogHeader>
              <Textarea
                value={configYaml}
                onChange={(e) => setConfigYaml(e.target.value)}
                className="h-[400px] font-mono text-sm"
                placeholder="Loading configuration..."
              />
              <DialogFooter>
                <Button variant="outline" onClick={() => setConfigDialogOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={saveConfigYaml}>
                  <Save className="h-4 w-4 mr-2" />
                  Save Config
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <p className="text-xs text-muted-foreground mt-2">
            Warning: Editing the raw config can break your setup. Make sure you know what you're doing.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
