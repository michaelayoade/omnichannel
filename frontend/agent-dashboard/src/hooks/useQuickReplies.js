import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getQuickReplies, createQuickReply, updateQuickReply, deleteQuickReply } from '../api';

const QUICK_REPLIES_KEY = ['quick-replies'];

export const useQuickReplies = () => {
  const queryClient = useQueryClient();

  // Fetch list
  const { data, isLoading, error } = useQuery(QUICK_REPLIES_KEY, async () => {
    const response = await getQuickReplies();
    return response.data;
  });

  // Create
  const createMutation = useMutation(createQuickReply, {
    onSuccess: () => queryClient.invalidateQueries(QUICK_REPLIES_KEY)
  });

  const updateMutation = useMutation(({ id, ...payload }) => updateQuickReply(id, payload), {
    onSuccess: () => queryClient.invalidateQueries(QUICK_REPLIES_KEY)
  });

  const deleteMutation = useMutation(deleteQuickReply, {
    onSuccess: () => queryClient.invalidateQueries(QUICK_REPLIES_KEY)
  });

  return {
    replies: data || [],
    isLoading,
    error,
    createReply: createMutation.mutateAsync,
    updateReply: updateMutation.mutateAsync,
    deleteReply: deleteMutation.mutateAsync,
  };
};
