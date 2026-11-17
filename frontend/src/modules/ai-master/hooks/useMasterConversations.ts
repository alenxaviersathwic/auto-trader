import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createConversation,
  deleteConversation,
  searchConversations,
  updateConversation,
} from "../api/master.api";
import { ConversationFilter, ConversationUpdate } from "../types/master.types";
import { masterQueryKeys } from "../queryKeys/masterQueryKeys";

const DEFAULT_FILTER: ConversationFilter = {
  page: 0,
  limit: 50,
  sortBy: "lastMessageAt",
  sortDir: "desc",
};

export function useMasterConversations() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<ConversationFilter>(DEFAULT_FILTER);

  const listQuery = useQuery({
    queryKey: masterQueryKeys.conversations.list(filter),
    queryFn: () => searchConversations(filter),
    placeholderData: keepPreviousData,
  });

  const createMutation = useMutation({
    mutationFn: (title?: string) => createConversation({ title }),
    onSuccess: () => qc.invalidateQueries({ queryKey: masterQueryKeys.conversations.all }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ConversationUpdate }) =>
      updateConversation(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: masterQueryKeys.conversations.all }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: masterQueryKeys.conversations.all }),
  });

  return { listQuery, filter, setFilter, createMutation, updateMutation, deleteMutation };
}
