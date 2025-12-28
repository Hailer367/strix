'use client';

import { useMemo } from 'react';
import { useStrixStore } from '@/lib/store';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Bot,
  Bug,
  Zap,
  Clock,
  Target,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Activity,
} from 'lucide-react';
import { formatDuration, intervalToDuration } from 'date-fns';

export function StatsPanel() {
  const { currentScan, agents, vulnerabilities } = useStrixStore();

  const stats = useMemo(() => {
    const agentList = Object.values(agents);
    const totalAgents = agentList.length;
    const activeAgents = agentList.filter(
      (a) => a.status === 'running' || a.status === 'waiting'
    ).length;
    const completedAgents = agentList.filter((a) => a.status === 'completed').length;
    const failedAgents = agentList.filter(
      (a) => a.status === 'failed' || a.status === 'llm_failed'
    ).length;
    const totalIterations = agentList.reduce((sum, a) => sum + a.iteration, 0);
    const maxIterations = agentList.reduce((sum, a) => sum + a.maxIterations, 0);

    const criticalVulns = vulnerabilities.filter((v) => v.severity === 'critical').length;
    const highVulns = vulnerabilities.filter((v) => v.severity === 'high').length;
    const mediumVulns = vulnerabilities.filter((v) => v.severity === 'medium').length;
    const lowVulns = vulnerabilities.filter((v) => v.severity === 'low').length;

    const scanDuration = currentScan
      ? Math.floor(
          (new Date().getTime() - new Date(currentScan.createdAt).getTime()) / 1000
        )
      : 0;

    return {
      totalAgents,
      activeAgents,
      completedAgents,
      failedAgents,
      totalIterations,
      maxIterations,
      criticalVulns,
      highVulns,
      mediumVulns,
      lowVulns,
      totalVulns: vulnerabilities.length,
      scanDuration,
      targetsCount: currentScan?.targets.length || 0,
    };
  }, [agents, vulnerabilities, currentScan]);

  const formattedDuration = formatDuration(
    intervalToDuration({ start: 0, end: stats.scanDuration * 1000 }),
    { format: ['hours', 'minutes', 'seconds'] }
  );

  const iterationProgress =
    stats.maxIterations > 0 ? (stats.totalIterations / stats.maxIterations) * 100 : 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 p-3">
      {/* Agents */}
      <Card className="bg-gradient-to-br from-blue-500/10 to-transparent border-blue-500/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Bot className="h-4 w-4 text-blue-500" />
            Agents
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {stats.activeAgents}
            <span className="text-muted-foreground text-sm font-normal">
              /{stats.totalAgents}
            </span>
          </div>
          <div className="flex gap-2 mt-1">
            <span className="text-xs text-green-500 flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3" />
              {stats.completedAgents}
            </span>
            {stats.failedAgents > 0 && (
              <span className="text-xs text-red-500 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {stats.failedAgents}
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Iterations */}
      <Card className="bg-gradient-to-br from-yellow-500/10 to-transparent border-yellow-500/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Zap className="h-4 w-4 text-yellow-500" />
            Iterations
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalIterations.toLocaleString()}</div>
          <Progress value={iterationProgress} className="h-1 mt-2" />
          <p className="text-xs text-muted-foreground mt-1">
            {iterationProgress.toFixed(1)}% of max capacity
          </p>
        </CardContent>
      </Card>

      {/* Vulnerabilities */}
      <Card className="bg-gradient-to-br from-red-500/10 to-transparent border-red-500/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Bug className="h-4 w-4 text-red-500" />
            Vulnerabilities
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalVulns}</div>
          <div className="flex gap-2 mt-1 flex-wrap">
            {stats.criticalVulns > 0 && (
              <span className="text-xs bg-red-600 text-white px-1.5 py-0.5 rounded">
                {stats.criticalVulns} Critical
              </span>
            )}
            {stats.highVulns > 0 && (
              <span className="text-xs bg-orange-500 text-white px-1.5 py-0.5 rounded">
                {stats.highVulns} High
              </span>
            )}
            {stats.mediumVulns > 0 && (
              <span className="text-xs bg-yellow-500 text-black px-1.5 py-0.5 rounded">
                {stats.mediumVulns} Med
              </span>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Duration */}
      <Card className="bg-gradient-to-br from-green-500/10 to-transparent border-green-500/30">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm flex items-center gap-2">
            <Clock className="h-4 w-4 text-green-500" />
            Duration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{formattedDuration || '0s'}</div>
          <div className="flex items-center gap-2 mt-1">
            <Target className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {stats.targetsCount} target{stats.targetsCount !== 1 ? 's' : ''}
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
