import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { ViewerProvider } from '../state/viewer'

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchInterval: false, staleTime: Infinity },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(ui: ReactNode, client = makeQueryClient()) {
  const result = render(
    <QueryClientProvider client={client}>
      <ViewerProvider>{ui}</ViewerProvider>
    </QueryClientProvider>,
  )
  return { client, ...result }
}
