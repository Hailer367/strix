'use client'

import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { fetchHistory } from '@/lib/api'
import type { HistoricalData } from '@/types'

export function TokenUsageChart() {
  const [data, setData] = useState<HistoricalData[]>([])

  useEffect(() => {
    const loadData = async () => {
      try {
        const history = await fetchHistory('tokens', 3600)
        setData(history)
      } catch (error) {
        console.error('Failed to load history:', error)
      }
    }

    loadData()
    const interval = setInterval(loadData, 30000) // Refresh every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const chartData = data.map((point) => ({
    time: new Date(point.timestamp).toLocaleTimeString(),
    input: point.tokens?.input || 0,
    output: point.tokens?.output || 0,
    cached: point.tokens?.cached || 0,
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Token Usage Over Time</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="time" stroke="#9CA3AF" fontSize={12} />
            <YAxis stroke="#9CA3AF" fontSize={12} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '6px',
              }}
            />
            <Area
              type="monotone"
              dataKey="input"
              stackId="1"
              stroke="#22C55E"
              fill="#22C55E"
              fillOpacity={0.6}
            />
            <Area
              type="monotone"
              dataKey="output"
              stackId="1"
              stroke="#3B82F6"
              fill="#3B82F6"
              fillOpacity={0.6}
            />
            <Area
              type="monotone"
              dataKey="cached"
              stackId="1"
              stroke="#F59E0B"
              fill="#F59E0B"
              fillOpacity={0.6}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}