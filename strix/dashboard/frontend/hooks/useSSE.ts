import { useEffect, useState, useCallback, useRef } from 'react'
import type { DashboardState } from '@/types'

interface UseSSEOptions {
  onUpdate?: (state: DashboardState) => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

export function useSSE(options: UseSSEOptions = {}) {
  const {
    onUpdate,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options

  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [state, setState] = useState<DashboardState | null>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef<NodeJS.Timeout | null>(null)

  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }

    try {
      const eventSource = new EventSource('/api/stream')
      eventSourceRef.current = eventSource

      eventSource.onopen = () => {
        setConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
      }

      eventSource.addEventListener('state', (e) => {
        try {
          const data = JSON.parse(e.data) as DashboardState
          setState(data)
          onUpdate?.(data)
        } catch (err) {
          console.error('Failed to parse state:', err)
        }
      })

      eventSource.addEventListener('update', (e) => {
        try {
          const data = JSON.parse(e.data) as DashboardState
          setState((prev) => ({ ...prev, ...data }))
          onUpdate?.(data)
        } catch (err) {
          console.error('Failed to parse update:', err)
        }
      })

      eventSource.onerror = () => {
        setConnected(false)
        eventSource.close()

        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          reconnectTimerRef.current = setTimeout(() => {
            connect()
          }, reconnectInterval)
        } else {
          setError(new Error('Max reconnection attempts reached'))
        }
      }
    } catch (err) {
      setError(err as Error)
      setConnected(false)
    }
  }, [onUpdate, reconnectInterval, maxReconnectAttempts])

  useEffect(() => {
    // Initial fetch
    fetch('/api/state')
      .then((r) => r.json())
      .then((data) => {
        setState(data as DashboardState)
        onUpdate?.(data as DashboardState)
      })
      .catch((err) => {
        console.error('Failed to fetch initial state:', err)
      })

    connect()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
        eventSourceRef.current = null
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
      }
    }
  }, [connect])

  return { connected, error, state, reconnect: connect }
}