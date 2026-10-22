import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  confirmProposal,
  rejectProposal,
  revalidateProposal,
  searchProposals,
} from "../api/master.api";
import { ConfirmProposalRequest, ProposalFilter } from "../types/master.types";
import { masterQueryKeys } from "../queryKeys/masterQueryKeys";

export function useMasterProposals(conversationId: number | null) {
  const qc = useQueryClient();
  const filter: ProposalFilter = {
    page: 0,
    limit: 20,
    sortBy: "createdAt",
    sortDir: "desc",
    conversationId: conversationId ?? undefined,
    proposalStatus: "PENDING",
  };

  const proposalsQuery = useQuery({
    queryKey: masterQueryKeys.proposals.list(filter),
    queryFn: () => searchProposals(filter),
    enabled: conversationId !== null,
    refetchInterval: 5000,
  });

  const confirmMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ConfirmProposalRequest }) =>
      confirmProposal(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: masterQueryKeys.proposals.all });
      qc.invalidateQueries({ queryKey: masterQueryKeys.messages.all });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: number; reason?: string }) =>
      rejectProposal(id, { reason }),
    onSuccess: () => qc.invalidateQueries({ queryKey: masterQueryKeys.proposals.all }),
  });

  const revalidateMutation = useMutation({
    mutationFn: (id: number) => revalidateProposal(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: masterQueryKeys.proposals.all }),
  });

  return { proposalsQuery, confirmMutation, rejectMutation, revalidateMutation };
}
