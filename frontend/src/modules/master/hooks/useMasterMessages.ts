import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { searchMessages, sendMessage } from "../api/master.api";
import { MessageFilter, SendMessageRequest } from "../types/master.types";
import { masterQueryKeys } from "../queryKeys/masterQueryKeys";

const DEFAULT_FILTER: MessageFilter = { page: 0, limit: 100, sortBy: "seq", sortDir: "asc" };

export function useMasterMessages(conversationId: number | null) {
  const qc = useQueryClient();
  const filter: MessageFilter = { ...DEFAULT_FILTER, conversationId: conversationId ?? undefined };

  const messagesQuery = useQuery({
    queryKey: masterQueryKeys.messages.list(conversationId ?? 0, filter),
    queryFn: () => searchMessages(conversationId!, filter),
    enabled: conversationId !== null,
    placeholderData: keepPreviousData,
    refetchInterval: false,
  });

  const sendMutation = useMutation({
    mutationFn: (payload: SendMessageRequest) => sendMessage(conversationId!, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: masterQueryKeys.messages.list(conversationId ?? 0, filter) });
      qc.invalidateQueries({ queryKey: masterQueryKeys.conversations.all });
    },
  });

  return { messagesQuery, sendMutation };
}
