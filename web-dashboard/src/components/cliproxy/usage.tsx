'use client';

import { useState, useEffect, useMemo } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI, UsageStatistics } from '@/lib/cliproxy-api';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import {
  BarChart3,
  Download,
  Upload,
  RefreshCw,
  Loader2,
  TrendingUp,
  TrendingDown,
  Zap,
  Clock,
  CheckCircle,
  XCircle,
  Activity,
  Calendar,
} from 'lucide-react';

interface UsageBreakdown {
  api: string;
  model: string;
  requests: number;
  tokens: number;
  successRate: number;
}

export function CLIProxyUsage() {
  const { cliProxyConnected, cliProxyUsage, setCLIProxyUsage } = useStrixStore();
  const [loading, setLoading] = useState(false);
  const [detailedUsage, setDetailedUsage] = useState<UsageStatistics | null>(null);
  const [timeRange, setTimeRange] = useState<'today' | 'week' | 'month' | 'all'>('all');

  // Fetch detailed usage
  const fetchUsage = async () => {
    if (!cliProxyConnected) return;
    
    setLoading(true);
    try {
      const usage = await cliProxyAPI.getUsage();
      setDetailedUsage(usage);
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
    } catch (error) {
      console.error('Failed to fetch usage:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, [cliProxyConnected]);

  // Export usage data
  const handleExport = async () => {
    try {
      const data = await cliProxyAPI.exportUsage();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `cliproxy-usage-${new Date().toISOString().split('T')[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to export usage:', error);
    }
  };

  // Process usage breakdown
  const usageBreakdown = useMemo<UsageBreakdown[]>(() => {
    if (!detailedUsage?.usage.apis) return [];

    const breakdown: UsageBreakdown[] = [];
    
    Object.entries(detailedUsage.usage.apis).forEach(([api, apiData]) => {
      if (apiData.models) {
        Object.entries(apiData.models).forEach(([model, modelData]) => {
          const successCount = modelData.details?.filter(d => !d.failed).length || 0;
          const totalCount = modelData.details?.length || modelData.total_requests;
          
          breakdown.push({
            api,
            model,
            requests: modelData.total_requests,
            tokens: modelData.total_tokens,
            successRate: totalCount > 0 ? (successCount / totalCount) * 100 : 0,
          });
        });
      }
    });

    return breakdown.sort((a, b) => b.requests - a.requests);
  }, [detailedUsage]);

  // Calculate hourly distribution
  const hourlyDistribution = useMemo(() => {
    if (!cliProxyUsage?.requestsByHour) return [];
    
    return Object.entries(cliProxyUsage.requestsByHour)
      .map(([hour, count]) => ({
        hour: parseInt(hour),
        requests: count,
      }))
      .sort((a, b) => a.hour - b.hour);
  }, [cliProxyUsage]);

  // Calculate daily distribution
  const dailyDistribution = useMemo(() => {
    if (!cliProxyUsage?.requestsByDay) return [];
    
    return Object.entries(cliProxyUsage.requestsByDay)
      .map(([date, count]) => ({
        date,
        requests: count,
      }))
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-7);
  }, [cliProxyUsage]);

  if (!cliProxyConnected) {
    return (
      <Alert>
        <XCircle className="h-4 w-4" />
        <AlertTitle>Not Connected</AlertTitle>
        <AlertDescription>
          Please connect to CLIProxyAPI first to view usage statistics.
        </AlertDescription>
      </Alert>
    );
  }

  const successRate = cliProxyUsage && cliProxyUsage.totalRequests > 0
    ? (cliProxyUsage.successCount / cliProxyUsage.totalRequests) * 100
    : 0;

  return (
    <div className="space-y-6">
      {/* Header Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Usage Analytics</h3>
          <p className="text-sm text-muted-foreground">
            Monitor your API usage and performance metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={timeRange} onValueChange={(v) => setTimeRange(v as typeof timeRange)}>
            <SelectTrigger className="w-[120px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="today">Today</SelectItem>
              <SelectItem value="week">This Week</SelectItem>
              <SelectItem value="month">This Month</SelectItem>
              <SelectItem value="all">All Time</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
          <Button variant="outline" size="sm" onClick={fetchUsage} disabled={loading}>
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Requests</p>
                <p className="text-2xl font-bold">
                  {cliProxyUsage?.totalRequests.toLocaleString() || 0}
                </p>
              </div>
              <Zap className="h-8 w-8 text-yellow-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Success Rate</p>
                <p className="text-2xl font-bold">{successRate.toFixed(1)}%</p>
              </div>
              {successRate >= 95 ? (
                <TrendingUp className="h-8 w-8 text-green-500 opacity-50" />
              ) : (
                <TrendingDown className="h-8 w-8 text-red-500 opacity-50" />
              )}
            </div>
            <Progress value={successRate} className="mt-2" />
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Total Tokens</p>
                <p className="text-2xl font-bold">
                  {((cliProxyUsage?.totalTokens || 0) / 1000).toFixed(1)}K
                </p>
              </div>
              <Activity className="h-8 w-8 text-blue-500 opacity-50" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Failed Requests</p>
                <p className="text-2xl font-bold">
                  {cliProxyUsage?.failureCount.toLocaleString() || 0}
                </p>
              </div>
              <XCircle className="h-8 w-8 text-red-500 opacity-50" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Hourly Distribution */}
      {hourlyDistribution.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="h-5 w-5" />
              Requests by Hour
            </CardTitle>
            <CardDescription>
              Distribution of requests throughout the day
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1 h-32">
              {Array.from({ length: 24 }, (_, i) => {
                const hourData = hourlyDistribution.find(h => h.hour === i);
                const requests = hourData?.requests || 0;
                const maxRequests = Math.max(...hourlyDistribution.map(h => h.requests), 1);
                const height = (requests / maxRequests) * 100;
                
                return (
                  <div
                    key={i}
                    className="flex-1 flex flex-col items-center"
                    title={`${i}:00 - ${requests} requests`}
                  >
                    <div
                      className="w-full bg-primary/50 rounded-t transition-all hover:bg-primary"
                      style={{ height: `${height}%` }}
                    />
                    {i % 4 === 0 && (
                      <span className="text-xs text-muted-foreground mt-1">
                        {i}h
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Daily Distribution */}
      {dailyDistribution.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Requests by Day
            </CardTitle>
            <CardDescription>
              Daily request volume over the past week
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {dailyDistribution.map((day) => {
                const maxRequests = Math.max(...dailyDistribution.map(d => d.requests), 1);
                const width = (day.requests / maxRequests) * 100;
                
                return (
                  <div key={day.date} className="flex items-center gap-3">
                    <span className="text-sm text-muted-foreground w-24">
                      {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                    </span>
                    <div className="flex-1">
                      <div
                        className="h-6 bg-primary/50 rounded transition-all hover:bg-primary"
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className="text-sm font-medium w-16 text-right">
                      {day.requests.toLocaleString()}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Usage Breakdown by Model */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Usage by Model
          </CardTitle>
          <CardDescription>
            Breakdown of requests and tokens by model
          </CardDescription>
        </CardHeader>
        <CardContent>
          {usageBreakdown.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Model</TableHead>
                  <TableHead>API Endpoint</TableHead>
                  <TableHead className="text-right">Requests</TableHead>
                  <TableHead className="text-right">Tokens</TableHead>
                  <TableHead className="text-right">Success Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usageBreakdown.slice(0, 10).map((item, idx) => (
                  <TableRow key={idx}>
                    <TableCell className="font-medium">{item.model}</TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {item.api}
                    </TableCell>
                    <TableCell className="text-right">
                      {item.requests.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-right">
                      {(item.tokens / 1000).toFixed(1)}K
                    </TableCell>
                    <TableCell className="text-right">
                      <Badge
                        variant={item.successRate >= 95 ? 'default' : item.successRate >= 80 ? 'secondary' : 'destructive'}
                      >
                        {item.successRate.toFixed(1)}%
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8">
              <BarChart3 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No usage data available</p>
              <p className="text-sm text-muted-foreground">
                Usage statistics will appear here once you start making requests
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Token Breakdown */}
      {cliProxyUsage && (cliProxyUsage.tokensByDay && Object.keys(cliProxyUsage.tokensByDay).length > 0) && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Activity className="h-5 w-5" />
              Token Usage by Day
            </CardTitle>
            <CardDescription>
              Daily token consumption
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {Object.entries(cliProxyUsage.tokensByDay)
                .sort((a, b) => b[0].localeCompare(a[0]))
                .slice(0, 7)
                .map(([date, tokens]) => {
                  const maxTokens = Math.max(...Object.values(cliProxyUsage.tokensByDay), 1);
                  const width = (tokens / maxTokens) * 100;
                  
                  return (
                    <div key={date} className="flex items-center gap-3">
                      <span className="text-sm text-muted-foreground w-24">
                        {new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                      </span>
                      <div className="flex-1">
                        <div
                          className="h-6 bg-blue-500/50 rounded transition-all hover:bg-blue-500"
                          style={{ width: `${width}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-20 text-right">
                        {(tokens / 1000).toFixed(1)}K
                      </span>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
