'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI } from '@/lib/cliproxy-api';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
} from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Network,
  Users,
  BarChart3,
  Settings2,
  Shield,
  Zap,
  RefreshCw,
  CheckCircle,
  XCircle,
  Loader2,
  ExternalLink,
} from 'lucide-react';
import { CLIProxyAccounts } from './accounts';
import { CLIProxyUsage } from './usage';
import { CLIProxySettings } from './settings';
import { CLIProxyModels } from './models';
import { CLIProxyConnection } from './connection';

export function CLIProxyDashboard() {
  const { cliProxyConfig, setCLIProxyConfig, cliProxyConnected, setCLIProxyConnected, cliProxyUsage, setCLIProxyUsage } = useStrixStore();
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [latestVersion, setLatestVersion] = useState<string | null>(null);

  // Initialize API client with config
  useEffect(() => {
    cliProxyAPI.setBaseUrl(cliProxyConfig.baseUrl);
    cliProxyAPI.setManagementKey(cliProxyConfig.managementKey);
  }, [cliProxyConfig.baseUrl, cliProxyConfig.managementKey]);

  // Check connection and fetch initial data
  const checkConnection = async () => {
    setLoading(true);
    try {
      const isConnected = await cliProxyAPI.checkHealth();
      setCLIProxyConnected(isConnected);

      if (isConnected) {
        // Fetch usage stats
        try {
          const usage = await cliProxyAPI.getUsage();
          setCLIProxyUsage({
            totalRequests: usage.usage.total_requests,
            successCount: usage.usage.success_count,
            failureCount: usage.usage.failure_count,
            totalTokens: usage.usage.total_tokens,
            requestsByDay: usage.usage.requests_by_day,
            requestsByHour: usage.usage.requests_by_hour,
            tokensByDay: usage.usage.tokens_by_day,
            tokensByHour: usage.usage.tokens_by_hour,
            apis: {},
          });
        } catch (e) {
          console.error('Failed to fetch usage:', e);
        }

        // Fetch latest version
        try {
          const version = await cliProxyAPI.getLatestVersion();
          setLatestVersion(version['latest-version']);
        } catch (e) {
          console.error('Failed to fetch version:', e);
        }
      }
    } catch (error) {
      console.error('Connection check failed:', error);
      setCLIProxyConnected(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (cliProxyConfig.enabled) {
      checkConnection();
    }
  }, [cliProxyConfig.enabled, cliProxyConfig.baseUrl]);

  // Auto-refresh usage stats every 30 seconds when connected
  useEffect(() => {
    if (!cliProxyConnected) return;

    const interval = setInterval(async () => {
      try {
        const usage = await cliProxyAPI.getUsage();
        setCLIProxyUsage({
          totalRequests: usage.usage.total_requests,
          successCount: usage.usage.success_count,
          failureCount: usage.usage.failure_count,
          totalTokens: usage.usage.total_tokens,
          requestsByDay: usage.usage.requests_by_day,
          requestsByHour: usage.usage.requests_by_hour,
          tokensByDay: usage.usage.tokens_by_day,
          tokensByHour: usage.usage.tokens_by_hour,
          apis: {},
        });
      } catch (e) {
        console.error('Failed to refresh usage:', e);
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [cliProxyConnected, setCLIProxyUsage]);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-10 w-10 rounded-lg bg-gradient-to-br from-purple-500 to-blue-600">
            <Network className="h-5 w-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold flex items-center gap-2">
              CLIProxyAPI
              {latestVersion && (
                <Badge variant="outline" className="text-xs">
                  {latestVersion}
                </Badge>
              )}
            </h2>
            <p className="text-sm text-muted-foreground">
              Unified AI API Gateway - Access OpenAI, Gemini, Claude & More
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={checkConnection}
                  disabled={loading}
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RefreshCw className="h-4 w-4" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Refresh Connection</TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <Badge
            variant={cliProxyConnected ? 'default' : 'destructive'}
            className="flex items-center gap-1"
          >
            {cliProxyConnected ? (
              <>
                <CheckCircle className="h-3 w-3" />
                Connected
              </>
            ) : (
              <>
                <XCircle className="h-3 w-3" />
                Disconnected
              </>
            )}
          </Badge>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => window.open('https://help.router-for.me/', '_blank')}
                >
                  <ExternalLink className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>CLIProxyAPI Documentation</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {/* Quick Stats */}
      {cliProxyConnected && cliProxyUsage && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <Zap className="h-4 w-4 text-yellow-500" />
                <span className="text-sm text-muted-foreground">Total Requests</span>
              </div>
              <p className="text-2xl font-bold">{cliProxyUsage.totalRequests.toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm text-muted-foreground">Success Rate</span>
              </div>
              <p className="text-2xl font-bold">
                {cliProxyUsage.totalRequests > 0
                  ? ((cliProxyUsage.successCount / cliProxyUsage.totalRequests) * 100).toFixed(1)
                  : '0'}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-blue-500" />
                <span className="text-sm text-muted-foreground">Total Tokens</span>
              </div>
              <p className="text-2xl font-bold">{cliProxyUsage.totalTokens.toLocaleString()}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center gap-2">
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm text-muted-foreground">Failed Requests</span>
              </div>
              <p className="text-2xl font-bold">{cliProxyUsage.failureCount.toLocaleString()}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Main Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-5 lg:w-auto lg:inline-grid">
          <TabsTrigger value="overview" className="flex items-center gap-2">
            <Network className="h-4 w-4" />
            <span className="hidden sm:inline">Connection</span>
          </TabsTrigger>
          <TabsTrigger value="accounts" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            <span className="hidden sm:inline">Accounts</span>
          </TabsTrigger>
          <TabsTrigger value="models" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            <span className="hidden sm:inline">Models</span>
          </TabsTrigger>
          <TabsTrigger value="usage" className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4" />
            <span className="hidden sm:inline">Usage</span>
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            <span className="hidden sm:inline">Settings</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <CLIProxyConnection />
        </TabsContent>

        <TabsContent value="accounts" className="space-y-4">
          <CLIProxyAccounts />
        </TabsContent>

        <TabsContent value="models" className="space-y-4">
          <CLIProxyModels />
        </TabsContent>

        <TabsContent value="usage" className="space-y-4">
          <CLIProxyUsage />
        </TabsContent>

        <TabsContent value="settings" className="space-y-4">
          <CLIProxySettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}
