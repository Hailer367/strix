'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI, CLIProxyApiKey, OpenAICompatibilityProvider } from '@/lib/cliproxy-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
} from '@/components/ui/dialog';
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Users,
  Plus,
  Trash2,
  Edit,
  RefreshCw,
  Loader2,
  Key,
  ExternalLink,
  LogIn,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  Sparkles,
  Bot,
  Zap,
  Brain,
  Cloud,
} from 'lucide-react';

// Provider configurations with icons and colors
const PROVIDERS = {
  google: {
    name: 'Google (Gemini)',
    icon: Sparkles,
    color: 'from-blue-500 to-cyan-500',
    oauthSupported: true,
    apiKeySupported: true,
    description: 'Access Gemini models via OAuth or API key',
  },
  claude: {
    name: 'Anthropic (Claude)',
    icon: Bot,
    color: 'from-orange-500 to-amber-500',
    oauthSupported: true,
    apiKeySupported: true,
    description: 'Access Claude models via OAuth or API key',
  },
  openai: {
    name: 'OpenAI (GPT/Codex)',
    icon: Zap,
    color: 'from-green-500 to-emerald-500',
    oauthSupported: true,
    apiKeySupported: true,
    description: 'Access GPT and Codex models',
  },
  qwen: {
    name: 'Qwen (Alibaba)',
    icon: Brain,
    color: 'from-purple-500 to-pink-500',
    oauthSupported: true,
    apiKeySupported: false,
    description: 'Access Qwen models via OAuth',
  },
  iflow: {
    name: 'iFlow',
    icon: Cloud,
    color: 'from-indigo-500 to-violet-500',
    oauthSupported: true,
    apiKeySupported: false,
    description: 'Access iFlow AI models',
  },
};

interface AccountFormData {
  provider: keyof typeof PROVIDERS;
  apiKey: string;
  baseUrl: string;
  proxyUrl: string;
  excludedModels: string;
}

export function CLIProxyAccounts() {
  const { cliProxyConnected } = useStrixStore();
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  
  // Account lists
  const [geminiAccounts, setGeminiAccounts] = useState<CLIProxyApiKey[]>([]);
  const [claudeAccounts, setClaudeAccounts] = useState<CLIProxyApiKey[]>([]);
  const [codexAccounts, setCodexAccounts] = useState<CLIProxyApiKey[]>([]);
  const [compatibilityProviders, setCompatibilityProviders] = useState<OpenAICompatibilityProvider[]>([]);
  const [authFiles, setAuthFiles] = useState<string[]>([]);

  // Dialog state
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [formData, setFormData] = useState<AccountFormData>({
    provider: 'google',
    apiKey: '',
    baseUrl: '',
    proxyUrl: '',
    excludedModels: '',
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [saving, setSaving] = useState(false);

  // Fetch all accounts
  const fetchAccounts = async () => {
    if (!cliProxyConnected) return;
    
    setRefreshing(true);
    try {
      const [gemini, claude, codex, compatibility, auth] = await Promise.all([
        cliProxyAPI.getGeminiApiKeys().catch(() => ({ 'gemini-api-key': [] })),
        cliProxyAPI.getClaudeApiKeys().catch(() => ({ 'claude-api-key': [] })),
        cliProxyAPI.getCodexApiKeys().catch(() => ({ 'codex-api-key': [] })),
        cliProxyAPI.getOpenAICompatibility().catch(() => ({ 'openai-compatibility': [] })),
        cliProxyAPI.getAuthFiles().catch(() => ({ files: [] })),
      ]);

      setGeminiAccounts(gemini['gemini-api-key'] || []);
      setClaudeAccounts(claude['claude-api-key'] || []);
      setCodexAccounts(codex['codex-api-key'] || []);
      setCompatibilityProviders(compatibility['openai-compatibility'] || []);
      setAuthFiles(auth.files?.map(f => f.name) || []);
    } catch (error) {
      console.error('Failed to fetch accounts:', error);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, [cliProxyConnected]);

  // OAuth login
  const handleOAuthLogin = (provider: string) => {
    cliProxyAPI.initiateOAuthLogin(provider as 'google' | 'claude' | 'openai' | 'qwen' | 'iflow');
  };

  // Add API key
  const handleAddApiKey = async () => {
    setSaving(true);
    try {
      const account: CLIProxyApiKey = {
        apiKey: formData.apiKey,
        baseUrl: formData.baseUrl || undefined,
        proxyUrl: formData.proxyUrl || undefined,
        excludedModels: formData.excludedModels 
          ? formData.excludedModels.split(',').map(s => s.trim()) 
          : undefined,
      };

      switch (formData.provider) {
        case 'google':
          await cliProxyAPI.addGeminiApiKey(account);
          break;
        case 'claude':
          await cliProxyAPI.addClaudeApiKey(account);
          break;
        case 'openai':
          await cliProxyAPI.addCodexApiKey(account);
          break;
      }

      setAddDialogOpen(false);
      setFormData({ provider: 'google', apiKey: '', baseUrl: '', proxyUrl: '', excludedModels: '' });
      fetchAccounts();
    } catch (error) {
      console.error('Failed to add account:', error);
    } finally {
      setSaving(false);
    }
  };

  // Delete account
  const handleDeleteAccount = async (provider: string, apiKey: string) => {
    try {
      switch (provider) {
        case 'gemini':
          await cliProxyAPI.deleteGeminiApiKey(apiKey);
          break;
        case 'claude':
          await cliProxyAPI.deleteClaudeApiKey(apiKey);
          break;
        case 'codex':
          await cliProxyAPI.deleteCodexApiKey(apiKey);
          break;
      }
      fetchAccounts();
    } catch (error) {
      console.error('Failed to delete account:', error);
    }
  };

  // Mask API key for display
  const maskApiKey = (key: string) => {
    if (key.length <= 8) return key;
    return `${key.slice(0, 4)}...${key.slice(-4)}`;
  };

  if (!cliProxyConnected) {
    return (
      <Alert>
        <XCircle className="h-4 w-4" />
        <AlertTitle>Not Connected</AlertTitle>
        <AlertDescription>
          Please connect to CLIProxyAPI first to manage accounts.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* OAuth Login Cards */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <LogIn className="h-5 w-5" />
                OAuth Login
              </CardTitle>
              <CardDescription>
                Login with your existing accounts - no API keys required!
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {Object.entries(PROVIDERS).map(([key, provider]) => {
              if (!provider.oauthSupported) return null;
              const Icon = provider.icon;
              const hasAuth = authFiles.some(f => f.toLowerCase().includes(key));
              
              return (
                <div
                  key={key}
                  className="relative group"
                >
                  <div className={`
                    p-4 rounded-lg border transition-all cursor-pointer
                    hover:border-primary hover:shadow-lg
                    ${hasAuth ? 'border-green-500 bg-green-500/10' : 'border-border'}
                  `}
                  onClick={() => handleOAuthLogin(key)}
                  >
                    <div className={`
                      h-12 w-12 rounded-lg bg-gradient-to-br ${provider.color}
                      flex items-center justify-center mb-3
                    `}>
                      <Icon className="h-6 w-6 text-white" />
                    </div>
                    <p className="font-medium text-sm">{provider.name}</p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {hasAuth ? 'Connected' : 'Click to login'}
                    </p>
                    {hasAuth && (
                      <CheckCircle className="absolute top-2 right-2 h-4 w-4 text-green-500" />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-muted-foreground mt-4">
            OAuth login opens a browser window for secure authentication. Your credentials are stored locally.
          </p>
        </CardContent>
      </Card>

      {/* API Keys Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                API Keys
              </CardTitle>
              <CardDescription>
                Manage API keys for each provider
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={fetchAccounts}
                disabled={refreshing}
              >
                {refreshing ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
              </Button>
              <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
                <DialogTrigger asChild>
                  <Button size="sm">
                    <Plus className="h-4 w-4 mr-2" />
                    Add API Key
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Add API Key</DialogTitle>
                    <DialogDescription>
                      Add a new API key for a provider
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Provider</label>
                      <Select
                        value={formData.provider}
                        onValueChange={(v) => setFormData({ ...formData, provider: v as keyof typeof PROVIDERS })}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(PROVIDERS)
                            .filter(([_, p]) => p.apiKeySupported)
                            .map(([key, provider]) => (
                              <SelectItem key={key} value={key}>
                                {provider.name}
                              </SelectItem>
                            ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">API Key</label>
                      <div className="relative">
                        <Input
                          type={showApiKey ? 'text' : 'password'}
                          value={formData.apiKey}
                          onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                          placeholder="Enter API key..."
                          className="pr-10"
                        />
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </button>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Base URL (Optional)</label>
                      <Input
                        value={formData.baseUrl}
                        onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                        placeholder="Custom API endpoint..."
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Proxy URL (Optional)</label>
                      <Input
                        value={formData.proxyUrl}
                        onChange={(e) => setFormData({ ...formData, proxyUrl: e.target.value })}
                        placeholder="socks5://proxy:1080"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium">Excluded Models (Optional)</label>
                      <Input
                        value={formData.excludedModels}
                        onChange={(e) => setFormData({ ...formData, excludedModels: e.target.value })}
                        placeholder="model1, model2, model3"
                      />
                      <p className="text-xs text-muted-foreground">
                        Comma-separated list of models to exclude
                      </p>
                    </div>
                  </div>
                  <DialogFooter>
                    <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleAddApiKey} disabled={saving || !formData.apiKey}>
                      {saving ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Adding...
                        </>
                      ) : (
                        'Add Key'
                      )}
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Gemini Accounts */}
          {geminiAccounts.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-blue-500" />
                Gemini API Keys ({geminiAccounts.length})
              </h4>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>API Key</TableHead>
                    <TableHead>Base URL</TableHead>
                    <TableHead>Excluded Models</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {geminiAccounts.map((account, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-sm">
                        {maskApiKey(account.apiKey)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {account.baseUrl || 'Default'}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {account.excludedModels?.map((m, i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {m}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteAccount('gemini', account.apiKey)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Claude Accounts */}
          {claudeAccounts.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <Bot className="h-4 w-4 text-orange-500" />
                Claude API Keys ({claudeAccounts.length})
              </h4>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>API Key</TableHead>
                    <TableHead>Base URL</TableHead>
                    <TableHead>Excluded Models</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {claudeAccounts.map((account, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-sm">
                        {maskApiKey(account.apiKey)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {account.baseUrl || 'Default'}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {account.excludedModels?.map((m, i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {m}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteAccount('claude', account.apiKey)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Codex/OpenAI Accounts */}
          {codexAccounts.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-medium flex items-center gap-2">
                <Zap className="h-4 w-4 text-green-500" />
                OpenAI/Codex API Keys ({codexAccounts.length})
              </h4>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>API Key</TableHead>
                    <TableHead>Base URL</TableHead>
                    <TableHead>Excluded Models</TableHead>
                    <TableHead className="w-[100px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {codexAccounts.map((account, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="font-mono text-sm">
                        {maskApiKey(account.apiKey)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {account.baseUrl || 'Default'}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {account.excludedModels?.map((m, i) => (
                            <Badge key={i} variant="outline" className="text-xs">
                              {m}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteAccount('codex', account.apiKey)}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Empty State */}
          {geminiAccounts.length === 0 && claudeAccounts.length === 0 && codexAccounts.length === 0 && (
            <div className="text-center py-8">
              <Key className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No API keys configured</p>
              <p className="text-sm text-muted-foreground">
                Add API keys or use OAuth login to connect your accounts
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* OpenAI Compatibility Providers */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cloud className="h-5 w-5" />
            OpenAI-Compatible Providers
          </CardTitle>
          <CardDescription>
            Additional providers like OpenRouter, Together AI, etc.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {compatibilityProviders.length > 0 ? (
            <div className="space-y-4">
              {compatibilityProviders.map((provider, idx) => (
                <div
                  key={idx}
                  className="p-4 border rounded-lg flex items-center justify-between"
                >
                  <div>
                    <p className="font-medium">{provider.name}</p>
                    <p className="text-sm text-muted-foreground">{provider.baseUrl}</p>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {provider.models.slice(0, 5).map((m, i) => (
                        <Badge key={i} variant="secondary" className="text-xs">
                          {m.alias || m.name}
                        </Badge>
                      ))}
                      {provider.models.length > 5 && (
                        <Badge variant="outline" className="text-xs">
                          +{provider.models.length - 5} more
                        </Badge>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline">
                      {provider.apiKeyEntries.length} key(s)
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Cloud className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No compatibility providers configured</p>
              <p className="text-sm text-muted-foreground">
                Configure providers in the Settings tab
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
