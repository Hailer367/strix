'use client';

import { useState, useEffect } from 'react';
import { useStrixStore } from '@/lib/store';
import { cliProxyAPI, OpenAICompatibilityProvider } from '@/lib/cliproxy-api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import {
  Alert,
  AlertDescription,
  AlertTitle,
} from '@/components/ui/alert';
import {
  Shield,
  Plus,
  Trash2,
  RefreshCw,
  Loader2,
  CheckCircle,
  XCircle,
  Zap,
  Bot,
  Sparkles,
  Brain,
  Play,
  Search,
  Copy,
  ExternalLink,
  Settings2,
} from 'lucide-react';

// Model categories for organization
const MODEL_CATEGORIES = {
  'chat': { name: 'Chat Models', icon: Bot, description: 'Conversational AI models' },
  'code': { name: 'Code Models', icon: Zap, description: 'Code generation and completion' },
  'reasoning': { name: 'Reasoning Models', icon: Brain, description: 'Advanced reasoning capabilities' },
  'vision': { name: 'Vision Models', icon: Sparkles, description: 'Image understanding' },
};

interface ModelTest {
  model: string;
  status: 'pending' | 'testing' | 'success' | 'failed';
  response?: string;
  error?: string;
  latency?: number;
}

export function CLIProxyModels() {
  const { cliProxyConnected, settings, updateSettings } = useStrixStore();
  const [loading, setLoading] = useState(false);
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModel, setSelectedModel] = useState<string | null>(null);
  const [testPrompt, setTestPrompt] = useState('Hello! Can you briefly introduce yourself in one sentence?');
  
  // Model testing state
  const [modelTests, setModelTests] = useState<Record<string, ModelTest>>({});
  
  // OAuth excluded models
  const [oauthExcludedModels, setOauthExcludedModels] = useState<Record<string, string[]>>({});
  
  // Compatibility providers
  const [compatibilityProviders, setCompatibilityProviders] = useState<OpenAICompatibilityProvider[]>([]);
  
  // Add provider dialog
  const [addProviderDialogOpen, setAddProviderDialogOpen] = useState(false);
  const [newProvider, setNewProvider] = useState<{
    name: string;
    baseUrl: string;
    apiKey: string;
    models: string;
  }>({ name: '', baseUrl: '', apiKey: '', models: '' });
  const [saving, setSaving] = useState(false);

  // Fetch available models
  const fetchModels = async () => {
    if (!cliProxyConnected) return;
    
    setLoading(true);
    try {
      const [models, excluded, compatibility] = await Promise.all([
        cliProxyAPI.getAvailableModels(),
        cliProxyAPI.getOAuthExcludedModels().catch(() => ({ 'oauth-excluded-models': {} })),
        cliProxyAPI.getOpenAICompatibility().catch(() => ({ 'openai-compatibility': [] })),
      ]);
      
      setAvailableModels(models);
      setOauthExcludedModels(excluded['oauth-excluded-models'] || {});
      setCompatibilityProviders(compatibility['openai-compatibility'] || []);
    } catch (error) {
      console.error('Failed to fetch models:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModels();
  }, [cliProxyConnected]);

  // Filter models by search
  const filteredModels = availableModels.filter(model =>
    model.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Categorize models
  const categorizedModels = {
    gemini: filteredModels.filter(m => m.includes('gemini')),
    claude: filteredModels.filter(m => m.includes('claude')),
    gpt: filteredModels.filter(m => m.includes('gpt') || m.includes('o1') || m.includes('o3') || m.includes('codex')),
    other: filteredModels.filter(m => !m.includes('gemini') && !m.includes('claude') && !m.includes('gpt') && !m.includes('o1') && !m.includes('o3') && !m.includes('codex')),
  };

  // Test a model
  const testModel = async (model: string) => {
    setModelTests(prev => ({
      ...prev,
      [model]: { model, status: 'testing' }
    }));

    const startTime = Date.now();
    
    try {
      const result = await cliProxyAPI.testChatCompletion(model, testPrompt);
      const latency = Date.now() - startTime;
      
      setModelTests(prev => ({
        ...prev,
        [model]: {
          model,
          status: result.success ? 'success' : 'failed',
          response: result.response,
          error: result.error,
          latency,
        }
      }));
    } catch (error) {
      setModelTests(prev => ({
        ...prev,
        [model]: {
          model,
          status: 'failed',
          error: String(error),
          latency: Date.now() - startTime,
        }
      }));
    }
  };

  // Set as default model
  const setAsDefault = (model: string) => {
    updateSettings({ llmModel: model });
  };

  // Add OpenAI compatibility provider
  const addCompatibilityProvider = async () => {
    if (!newProvider.name || !newProvider.baseUrl || !newProvider.apiKey) return;
    
    setSaving(true);
    try {
      const provider: OpenAICompatibilityProvider = {
        name: newProvider.name,
        baseUrl: newProvider.baseUrl,
        apiKeyEntries: [{ apiKey: newProvider.apiKey }],
        models: newProvider.models.split(',').map(m => ({ name: m.trim(), alias: m.trim() })).filter(m => m.name),
      };
      
      await cliProxyAPI.addOpenAICompatibilityProvider(provider);
      setAddProviderDialogOpen(false);
      setNewProvider({ name: '', baseUrl: '', apiKey: '', models: '' });
      fetchModels();
    } catch (error) {
      console.error('Failed to add provider:', error);
    } finally {
      setSaving(false);
    }
  };

  // Delete compatibility provider
  const deleteCompatibilityProvider = async (name: string) => {
    try {
      await cliProxyAPI.deleteOpenAICompatibilityProvider(name);
      fetchModels();
    } catch (error) {
      console.error('Failed to delete provider:', error);
    }
  };

  // Copy model ID
  const copyModelId = (model: string) => {
    navigator.clipboard.writeText(model);
  };

  if (!cliProxyConnected) {
    return (
      <Alert>
        <XCircle className="h-4 w-4" />
        <AlertTitle>Not Connected</AlertTitle>
        <AlertDescription>
          Please connect to CLIProxyAPI first to view available models.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Model Configuration</h3>
          <p className="text-sm text-muted-foreground">
            Manage available models and test their availability
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchModels} disabled={loading}>
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </Button>
      </div>

      {/* Search & Current Default */}
      <div className="flex items-center gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search models..."
            className="pl-10"
          />
        </div>
        <div className="flex items-center gap-2 p-2 border rounded-lg bg-muted/50">
          <span className="text-sm text-muted-foreground">Default:</span>
          <Badge variant="default">{settings.llmModel || 'Not set'}</Badge>
        </div>
      </div>

      {/* Test Prompt */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <Play className="h-4 w-4" />
            Test Prompt
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={testPrompt}
            onChange={(e) => setTestPrompt(e.target.value)}
            placeholder="Enter a prompt to test models..."
            className="h-20"
          />
        </CardContent>
      </Card>

      {/* Models by Provider */}
      <Tabs defaultValue="all" className="space-y-4">
        <TabsList>
          <TabsTrigger value="all" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            All ({availableModels.length})
          </TabsTrigger>
          <TabsTrigger value="gemini" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Gemini ({categorizedModels.gemini.length})
          </TabsTrigger>
          <TabsTrigger value="claude" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            Claude ({categorizedModels.claude.length})
          </TabsTrigger>
          <TabsTrigger value="gpt" className="flex items-center gap-2">
            <Zap className="h-4 w-4" />
            GPT/Codex ({categorizedModels.gpt.length})
          </TabsTrigger>
          <TabsTrigger value="other" className="flex items-center gap-2">
            <Brain className="h-4 w-4" />
            Other ({categorizedModels.other.length})
          </TabsTrigger>
        </TabsList>

        {['all', 'gemini', 'claude', 'gpt', 'other'].map(category => (
          <TabsContent key={category} value={category} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(category === 'all' ? filteredModels : categorizedModels[category as keyof typeof categorizedModels]).map((model) => {
                const test = modelTests[model];
                const isDefault = settings.llmModel === model;
                
                return (
                  <Card key={model} className={isDefault ? 'border-primary' : ''}>
                    <CardContent className="pt-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <p className="font-mono text-sm truncate" title={model}>
                            {model}
                          </p>
                          {isDefault && (
                            <Badge variant="default" className="mt-1">Default</Badge>
                          )}
                          {test && (
                            <div className="mt-2">
                              {test.status === 'testing' && (
                                <Badge variant="secondary" className="flex items-center gap-1 w-fit">
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                  Testing...
                                </Badge>
                              )}
                              {test.status === 'success' && (
                                <div className="space-y-1">
                                  <Badge variant="default" className="flex items-center gap-1 w-fit">
                                    <CheckCircle className="h-3 w-3" />
                                    {test.latency}ms
                                  </Badge>
                                  {test.response && (
                                    <p className="text-xs text-muted-foreground line-clamp-2">
                                      {test.response}
                                    </p>
                                  )}
                                </div>
                              )}
                              {test.status === 'failed' && (
                                <Badge variant="destructive" className="flex items-center gap-1 w-fit">
                                  <XCircle className="h-3 w-3" />
                                  Failed
                                </Badge>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => copyModelId(model)}
                            title="Copy model ID"
                          >
                            <Copy className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => testModel(model)}
                            disabled={test?.status === 'testing'}
                            title="Test model"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                          <Button
                            variant={isDefault ? 'secondary' : 'ghost'}
                            size="icon"
                            onClick={() => setAsDefault(model)}
                            title="Set as default"
                          >
                            <Zap className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {((category === 'all' ? filteredModels : categorizedModels[category as keyof typeof categorizedModels]).length === 0) && (
              <div className="text-center py-8">
                <Shield className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">No models found</p>
                <p className="text-sm text-muted-foreground">
                  {searchQuery ? 'Try a different search term' : 'Add accounts or providers to see models'}
                </p>
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>

      {/* OpenAI Compatibility Providers */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="h-5 w-5" />
                Custom Providers
              </CardTitle>
              <CardDescription>
                Add OpenAI-compatible API providers (OpenRouter, Together AI, etc.)
              </CardDescription>
            </div>
            <Dialog open={addProviderDialogOpen} onOpenChange={setAddProviderDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="h-4 w-4 mr-2" />
                  Add Provider
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Add Custom Provider</DialogTitle>
                  <DialogDescription>
                    Add an OpenAI-compatible API provider
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Provider Name</label>
                    <Input
                      value={newProvider.name}
                      onChange={(e) => setNewProvider({ ...newProvider, name: e.target.value })}
                      placeholder="e.g., OpenRouter"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Base URL</label>
                    <Input
                      value={newProvider.baseUrl}
                      onChange={(e) => setNewProvider({ ...newProvider, baseUrl: e.target.value })}
                      placeholder="https://openrouter.ai/api/v1"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">API Key</label>
                    <Input
                      type="password"
                      value={newProvider.apiKey}
                      onChange={(e) => setNewProvider({ ...newProvider, apiKey: e.target.value })}
                      placeholder="sk-..."
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Models (comma-separated)</label>
                    <Textarea
                      value={newProvider.models}
                      onChange={(e) => setNewProvider({ ...newProvider, models: e.target.value })}
                      placeholder="gpt-4, claude-3-opus, gemini-pro"
                    />
                    <p className="text-xs text-muted-foreground">
                      List of model IDs available from this provider
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setAddProviderDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={addCompatibilityProvider} disabled={saving}>
                    {saving ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Adding...
                      </>
                    ) : (
                      'Add Provider'
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
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
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteCompatibilityProvider(provider.name)}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <Settings2 className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No custom providers configured</p>
              <p className="text-sm text-muted-foreground">
                Add providers like OpenRouter, Together AI, or any OpenAI-compatible API
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* OAuth Excluded Models */}
      {Object.keys(oauthExcludedModels).length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              OAuth Excluded Models
            </CardTitle>
            <CardDescription>
              Models excluded from OAuth-based provider access
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(oauthExcludedModels).map(([provider, models]) => (
                <div key={provider} className="flex items-start gap-4">
                  <Badge variant="outline" className="capitalize">
                    {provider}
                  </Badge>
                  <div className="flex flex-wrap gap-1">
                    {models.map((model, idx) => (
                      <Badge key={idx} variant="secondary" className="text-xs">
                        {model}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
