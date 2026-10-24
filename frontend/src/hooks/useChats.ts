import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, createChat, deleteChat, getChat, listChats, patchChat } from '../api/client'
import type { Chat } from '../api/types'

export function useChats() {
  return useQuery({ queryKey: ['chats'], queryFn: listChats })
}

export function useChat(id: string | null) {
  return useQuery({
    queryKey: ['chat', id],
    queryFn: () => getChat(id as string),
    enabled: id !== null,
    retry: (count, error) => !(error instanceof ApiError && error.status === 404) && count < 1,
  })
}

export function useCreateChat() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createChat,
    onSuccess: (chat) => {
      queryClient.setQueryData<Chat>(['chat', chat.id], chat)
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    },
  })
}

export function usePatchScope(chatId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (document_ids: string[]) => patchChat(chatId, { document_ids }),
    onMutate: async (document_ids) => {
      await queryClient.cancelQueries({ queryKey: ['chat', chatId] })
      const previous = queryClient.getQueryData<Chat>(['chat', chatId])
      if (previous) queryClient.setQueryData<Chat>(['chat', chatId], { ...previous, document_ids })
      return { previous }
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(['chat', chatId], context.previous)
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    },
  })
}

export function useDeleteChat() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteChat,
    onSuccess: (_result, id) => {
      queryClient.removeQueries({ queryKey: ['chat', id] })
      void queryClient.invalidateQueries({ queryKey: ['chats'] })
    },
  })
}
