import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteDocument, listDocuments, uploadDocuments } from '../api/client'
import { useViewer } from '../state/viewer'

export function useDocuments() {
  return useQuery({
    queryKey: ['documents'],
    queryFn: listDocuments,
    refetchInterval: (q) => (q.state.data?.some((d) => d.status === 'processing') ? 1500 : false),
  })
}

export function useUploadDocuments() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadDocuments,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['documents'] }),
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  const viewer = useViewer()
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: (_result, id) => {
      if (viewer.active?.document_id === id) viewer.close()
      void queryClient.invalidateQueries({ queryKey: ['documents'] })
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
      void queryClient.invalidateQueries({ queryKey: ['chat'] })
    },
  })
}
