'use client';

import { useState } from 'react';
import { useStrixStore, Target } from '@/lib/store';
import { useStrixWebSocket } from '@/lib/websocket';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Play,
  Square,
  Plus,
  X,
  Globe,
  GitBranch,
  FolderCode,
  Network,
  Zap,
  Target as TargetIcon,
  Shield,
  Clock,
  Bot,
  Bug,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { formatDistanceToNow, formatDuration, intervalToDuration } from 'date-fns';
import { v4 as uuidv4 } from 'uuid';

const TARGET_TYPES = [
  { value: 'web_application', label: 'URL / Domain', icon: Globe },
  { value: 'repository', label: 'Repository', icon: GitBranch },
  { value: 'local_code', label: 'Local Code', icon: FolderCode },
  { value: 'ip_address', label: 'IP Address', icon: Network },
];

const SCAN_MODES = [
  {
    value: 'quick',
    label: 'Quick',
    description: 'Fast CI/CD checks (~10 min)',
    icon: Zap,
  },
  {
    value: 'standard',
    label: 'Standard',
    description: 'Routine testing (~30 min)',
    icon: TargetIcon,
  },
  {
    value: 'deep',
    label: 'Deep',
    description: 'Thorough security review (~2+ hours)',
    icon: Shield,
  },
];

interface NewTargetFormProps {
  onAdd: (target: Omit<Target, 'id' | 'status'>) => void;
}

function NewTargetForm({ onAdd }: NewTargetFormProps) {
  const [type, setType] = useState<Target['type']>('web_application');
  const [value, setValue] = useState('');

  const handleAdd = () => {
    if (!value.trim()) return;
    onAdd({ type, value: value.trim() });
    setValue('');
  };

  const Icon = TARGET_TYPES.find((t) => t.value === type)?.icon || Globe;

  return (
    <div className="flex gap-2">
      <Select value={type} onValueChange={(v) => setType(v as Target['type'])}>
        <SelectTrigger className="w-[160px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {TARGET_TYPES.map((t) => (
            <SelectItem key={t.value} value={t.value}>
              <div className="flex items-center gap-2">
                <t.icon className="h-4 w-4" />
                {t.label}
              </div>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="relative flex-1">
        <Icon className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={
            type === 'web_application'
              ? 'https://example.com'
              : type === 'repository'
              ? 'https://github.com/user/repo'
              : type === 'ip_address'
              ? '192.168.1.1'
              : '/path/to/code'
          }
          className="pl-8"
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
        />
      </div>
      <Button onClick={handleAdd} disabled={!value.trim()}>
        <Plus className="h-4 w-4" />
      </Button>
    </div>
  );
}

export function ScanControl() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [targets, setTargets] = useState<Array<Omit<Target, 'status'> & { id: string }>>([]);
  const [scanMode, setScanMode] = useState<'quick' | 'standard' | 'deep'>('deep');
  const [instructions, setInstructions] = useState('');
  const [scanName, setScanName] = useState('');

  const { currentScan, createScan, stopScan, agents, vulnerabilities, connected } = useStrixStore();
  const { startScan: wsStartScan, stopScan: wsStopScan } = useStrixWebSocket();

  const addTarget = (target: Omit<Target, 'id' | 'status'>) => {
    setTargets([...targets, { ...target, id: uuidv4() }]);
  };

  const removeTarget = (id: string) => {
    setTargets(targets.filter((t) => t.id !== id));
  };

  const handleStartScan = () => {
    if (targets.length === 0) return;

    const scan = createScan({
      name: scanName || `Scan ${new Date().toLocaleDateString()}`,
      targets: targets.map((t) => ({
        ...t,
        status: 'pending',
      })),
      status: 'running',
      mode: scanMode,
      instructions,
    });

    wsStartScan({
      targets: targets.map((t) => ({ type: t.type, value: t.value })),
      mode: scanMode,
      instructions,
      name: scan.name,
    });

    setDialogOpen(false);
    setTargets([]);
    setInstructions('');
    setScanName('');
  };

  const handleStopScan = () => {
    if (currentScan) {
      stopScan(currentScan.id);
      wsStopScan(currentScan.id);
    }
  };

  // Calculate stats
  const activeAgents = Object.values(agents).filter(
    (a) => a.status === 'running' || a.status === 'waiting'
  ).length;
  const totalAgents = Object.keys(agents).length;
  const totalIterations = Object.values(agents).reduce((sum, a) => sum + a.iteration, 0);

  const scanDuration = currentScan
    ? Math.floor(
        (new Date().getTime() - new Date(currentScan.createdAt).getTime()) / 1000
      )
    : 0;

  const formattedDuration = formatDuration(
    intervalToDuration({ start: 0, end: scanDuration * 1000 }),
    { format: ['hours', 'minutes', 'seconds'] }
  );

  return (
    <Card className="border-green-500/50 bg-gradient-to-br from-green-500/5 to-transparent">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-full bg-green-500/20">
              <Shield className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <CardTitle className="text-lg">
                {currentScan ? currentScan.name : 'Strix Security Scanner'}
              </CardTitle>
              <CardDescription>
                {currentScan
                  ? `Started ${formatDistanceToNow(new Date(currentScan.createdAt), { addSuffix: true })}`
                  : 'Ready to scan'}
              </CardDescription>
            </div>
          </div>

          {!currentScan || currentScan.status !== 'running' ? (
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button
                  className="bg-green-600 hover:bg-green-700"
                  disabled={!connected}
                >
                  <Play className="h-4 w-4 mr-2" />
                  New Scan
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Start New Security Scan</DialogTitle>
                  <DialogDescription>
                    Configure your penetration test targets and parameters
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-6 py-4">
                  {/* Scan Name */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Scan Name</label>
                    <Input
                      value={scanName}
                      onChange={(e) => setScanName(e.target.value)}
                      placeholder="My Security Scan"
                    />
                  </div>

                  {/* Targets */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Targets</label>
                    <NewTargetForm onAdd={addTarget} />
                    {targets.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {targets.map((target) => {
                          const Icon =
                            TARGET_TYPES.find((t) => t.value === target.type)?.icon ||
                            Globe;
                          return (
                            <Badge
                              key={target.id}
                              variant="secondary"
                              className="flex items-center gap-1 py-1.5"
                            >
                              <Icon className="h-3 w-3" />
                              <span className="max-w-[200px] truncate">
                                {target.value}
                              </span>
                              <button
                                onClick={() => removeTarget(target.id)}
                                className="ml-1 hover:text-destructive"
                              >
                                <X className="h-3 w-3" />
                              </button>
                            </Badge>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {/* Scan Mode */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Scan Mode</label>
                    <div className="grid grid-cols-3 gap-3">
                      {SCAN_MODES.map((mode) => (
                        <button
                          key={mode.value}
                          onClick={() =>
                            setScanMode(mode.value as 'quick' | 'standard' | 'deep')
                          }
                          className={cn(
                            'flex flex-col items-center p-4 rounded-lg border-2 transition-all',
                            scanMode === mode.value
                              ? 'border-green-500 bg-green-500/10'
                              : 'border-muted hover:border-muted-foreground/50'
                          )}
                        >
                          <mode.icon
                            className={cn(
                              'h-6 w-6 mb-2',
                              scanMode === mode.value
                                ? 'text-green-500'
                                : 'text-muted-foreground'
                            )}
                          />
                          <span className="font-medium text-sm">{mode.label}</span>
                          <span className="text-xs text-muted-foreground text-center mt-1">
                            {mode.description}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Instructions */}
                  <div className="space-y-2">
                    <label className="text-sm font-medium">
                      Custom Instructions (Optional)
                    </label>
                    <Textarea
                      value={instructions}
                      onChange={(e) => setInstructions(e.target.value)}
                      placeholder="Focus on authentication vulnerabilities, use credentials admin:password123..."
                      rows={3}
                    />
                  </div>
                </div>

                <DialogFooter>
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button
                    className="bg-green-600 hover:bg-green-700"
                    onClick={handleStartScan}
                    disabled={targets.length === 0}
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Start Scan
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          ) : (
            <Button variant="destructive" onClick={handleStopScan}>
              <Square className="h-4 w-4 mr-2" />
              Stop Scan
            </Button>
          )}
        </div>
      </CardHeader>

      {currentScan && currentScan.status === 'running' && (
        <CardContent className="pt-0">
          {/* Status indicators */}
          <div className="grid grid-cols-4 gap-4 mb-4">
            <div className="flex items-center gap-2">
              <Bot className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Agents</p>
                <p className="font-semibold">
                  {activeAgents}/{totalAgents}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Iterations</p>
                <p className="font-semibold">{totalIterations}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Bug className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Vulnerabilities</p>
                <p className="font-semibold">{vulnerabilities.length}</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Duration</p>
                <p className="font-semibold">{formattedDuration || '0s'}</p>
              </div>
            </div>
          </div>

          {/* Progress indicator */}
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-green-500" />
            <span className="text-sm text-muted-foreground">
              Scanning in progress...
            </span>
          </div>
        </CardContent>
      )}

      {!connected && (
        <CardContent className="pt-0">
          <div className="flex items-center gap-2 text-yellow-500">
            <AlertTriangle className="h-4 w-4" />
            <span className="text-sm">Not connected to Strix server</span>
          </div>
        </CardContent>
      )}
    </Card>
  );
}
