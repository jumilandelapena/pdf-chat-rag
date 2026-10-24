import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { getHealth } from '../api/client'

const BANNER_AFTER_MS = 3000

/** Polls GET /health. Shows a "waking up" banner while the backend is unreachable. */
export function useBackendHealth() {
  const query = useQuery({
    queryKey: ['health'],
    queryFn: () => getHealth(AbortSignal.timeout(90_000)),
    retry: false,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => (q.state.status === 'success' && !q.state.error ? 30_000 : 5_000),
  })
  const healthy = query.isSuccess && !query.error
  const [waitedLong, setWaitedLong] = useState(false)
  useEffect(() => {
    if (healthy) {
      setWaitedLong(false)
      return undefined
    }
    const timer = setTimeout(() => setWaitedLong(true), BANNER_AFTER_MS)
    return () => clearTimeout(timer)
  }, [healthy])
  return { ready: healthy, health: healthy ? (query.data ?? null) : null, showBanner: !healthy && waitedLong }
}
