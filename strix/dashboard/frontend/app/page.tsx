'use client'

import { useSSE } from '@/hooks/useSSE'
import { useEffect, useState } from 'react'
import { ConnectionStatus } from '@/components/alerts/ConnectionStatus'
import { Header } from '@/components/layout/Header'
import { DashboardContent } from '@/components/dashboard/DashboardContent'
import { TooltipProvider } from '@/components/ui/tooltip'

export default function DashboardPage() {
  const { connected, error, state } = useSSE()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  if (!mounted) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-lg text-muted-foreground">Loading dashboard...</div>
      </div>
    )
  }

  return (
    <TooltipProvider>
      <div className="min-h-screen">
        <ConnectionStatus connected={connected} error={error} />
        <Header lastUpdate={state?.last_updated} scanConfig={state?.scan_config} />
        <main className="container mx-auto p-4">
          {state ? (
            <DashboardContent state={state} />
          ) : (
            <div className="flex items-center justify-center min-h-[400px]">
              <div className="text-muted-foreground">Waiting for data...</div>
            </div>
          )}
        </main>
      </div>
    </TooltipProvider>
  )
}