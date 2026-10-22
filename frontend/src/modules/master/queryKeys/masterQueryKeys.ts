import { ConversationFilter, MessageFilter, ProposalFilter } from "../types/master.types";

export const masterQueryKeys = {
  all: ["master"] as const,

  conversations: {
    all: ["master", "conversations"] as const,
    list: (f: ConversationFilter) => ["master", "conversations", "list", f] as const,
    detail: (id: number) => ["master", "conversations", id] as const,
  },

  messages: {
    all: ["master", "messages"] as const,
    list: (conversationId: number, f: MessageFilter) =>
      ["master", "messages", conversationId, f] as const,
  },

  proposals: {
    all: ["master", "proposals"] as const,
    list: (f: ProposalFilter) => ["master", "proposals", "list", f] as const,
    detail: (id: number) => ["master", "proposals", id] as const,
  },

  health: ["master", "health"] as const,

  toolServers: ["master", "toolServers"] as const,
};
