import React, { useCallback, useEffect, useRef, useState } from "react";
import { Bot, Settings, ChevronRight } from "lucide-react";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { MessageBubble } from "../components/MessageBubble";
import { ThinkingIndicator } from "../components/ThinkingIndicator";
import { ProposalCard } from "../components/ProposalCard";
import { ChatInput } from "../components/ChatInput";
import { MasterHealthBadge } from "../components/MasterHealthBadge";
import { useMasterConversations } from "../hooks/useMasterConversations";
import { useMasterMessages } from "../hooks/useMasterMessages";
import { useMasterProposals } from "../hooks/useMasterProposals";
import { useMasterHealth } from "../hooks/useMasterHealth";
import { cancelRun, getRun } from "../api/master.api";
import {
  ConfirmMode,
  Message,
  RunState,
  SseEventType,
} from "../types/master.types";

export const MasterPage: React.FC = () => {
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [activeRunId, setActiveRunId] = useState<number | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [streamingContent, setStreamingContent] = useState("");
  const [thinkingEvent, setThinkingEvent] = useState<{ event?: SseEventType; label?: string } | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showProposals, setShowProposals] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { listQuery, createMutation, updateMutation, deleteMutation } = useMasterConversations();
  const { messagesQuery, sendMutation } = useMasterMessages(activeConvId);
  const { proposalsQuery, confirmMutation, rejectMutation, revalidateMutation } =
    useMasterProposals(activeConvId);
  const healthQuery = useMasterHealth();

  const isRunning = runState === "RUNNING" || runState === "PENDING";

  // ── Scroll to bottom when messages change ─────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesQuery.data, streamingContent, thinkingEvent]);

  // ── Run status polling (reliable; no missed SSE events) ───────────────────
  const pollTimerRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  const startPolling = useCallback((runId: number) => {
    stopPolling();
    let attempts = 0;
    const MAX_ATTEMPTS = 240; // ~2 minutes at 500ms

    const tick = async () => {
      attempts += 1;
      try {
        const run = await getRun(runId);
        const state = String(run.state);
        if (state === "RUNNING" || state === "PENDING") {
          setRunState("RUNNING");
          setThinkingEvent({ event: "thinking", label: "Master is thinking…" });
          if (attempts < MAX_ATTEMPTS) {
            pollTimerRef.current = window.setTimeout(tick, 500);
          } else {
            setThinkingEvent(null);
            setRunState("ERROR");
          }
          return;
        }

        setThinkingEvent(null);
        setStreamingContent("");
        messagesQuery.refetch();
        proposalsQuery.refetch();

        if (state === "COMPLETED") {
          setRunState("DONE");
        } else if (state === "WAITING_USER") {
          setRunState("AWAITING_CONFIRMATION");
        } else if (state === "CANCELLED") {
          setRunState("CANCELLED");
        } else {
          setRunState("ERROR");
        }
      } catch {
        if (attempts < MAX_ATTEMPTS) {
          pollTimerRef.current = window.setTimeout(tick, 1000);
        } else {
          setThinkingEvent(null);
          setRunState("ERROR");
        }
      }
    };

    tick();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Cleanup polling on unmount
  useEffect(() => () => { stopPolling(); }, []);

  // ── Actions ───────────────────────────────────────────────────────────────
  const handleNewConversation = async () => {
    const conv = await createMutation.mutateAsync(undefined);
    setActiveConvId(conv.id);
    setActiveRunId(null);
    setRunState(null);
    setStreamingContent("");
    setThinkingEvent(null);
  };

  const handleSelectConversation = (id: number) => {
    if (id === activeConvId) return;
    stopPolling();
    setActiveConvId(id);
    setActiveRunId(null);
    setRunState(null);
    setStreamingContent("");
    setThinkingEvent(null);
  };

  const handleDeleteConversation = async (id: number) => {
    await deleteMutation.mutateAsync(id);
    if (id === activeConvId) {
      setActiveConvId(null);
      setActiveRunId(null);
    }
  };

  const handleRenameConversation = (id: number, title: string) => {
    updateMutation.mutate({ id, payload: { title } });
  };

  const handleSend = async (text: string) => {
    if (!activeConvId) return;
    const result = await sendMutation.mutateAsync({ content: text });
    setActiveRunId(result.runId);
    setRunState("PENDING");
    startPolling(result.runId);
  };

  const handleChoice = async (choice: string) => {
    if (!activeConvId) return;
    const result = await sendMutation.mutateAsync({ content: choice, choice });
    setActiveRunId(result.runId);
    setRunState("PENDING");
    startPolling(result.runId);
  };

  const handleCancelRun = async () => {
    if (!activeRunId) return;
    stopPolling();
    await cancelRun(activeRunId);
    setRunState("CANCELLED");
    setThinkingEvent(null);
  };

  const handleConfirm = (id: number, mode: ConfirmMode, acked: string[], typed?: string) => {
    confirmMutation.mutate({ id, payload: { mode, acknowledgedComplicationCodes: acked, typedPhrase: typed } });
  };

  const handleReject = (id: number, reason?: string) => {
    rejectMutation.mutate({ id, reason });
  };

  const handleRevalidate = (id: number) => {
    revalidateMutation.mutate(id);
  };

  // ── Messages to render ────────────────────────────────────────────────────
  const messages: Message[] = messagesQuery.data?.list ?? [];
  const pendingProposals = proposalsQuery.data?.list?.filter((p) => p.proposalStatus === "PENDING") ?? [];

  return (
    <div className="master-page">
      {/* Sidebar toggle for small screens */}
      {!sidebarOpen && (
        <button className="master-sidebar-toggle" onClick={() => setSidebarOpen(true)}>
          <ChevronRight size={16} />
        </button>
      )}

      {/* Sidebar */}
      {sidebarOpen && (
        <ConversationSidebar
          data={listQuery.data}
          activeId={activeConvId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          onRename={handleRenameConversation}
          isCreating={createMutation.isPending}
        />
      )}

      {/* Main area */}
      <div className="master-main">
        {/* Topbar */}
        <div className="master-topbar">
          <div className="master-topbar-left">
            <button className="master-sidebar-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
              <Bot size={18} />
            </button>
            <div className="master-topbar-title">
              <span className="master-title-text">AI Master</span>
              <span className="master-subtitle">Strategy & Rules Assistant</span>
            </div>
          </div>
          <div className="master-topbar-right">
            <MasterHealthBadge health={healthQuery.data} isLoading={healthQuery.isLoading} />
            {pendingProposals.length > 0 && (
              <button
                id="master-proposals-toggle"
                className={`master-proposal-pill${showProposals ? " active" : ""}`}
                onClick={() => setShowProposals(!showProposals)}
              >
                {pendingProposals.length} pending proposal{pendingProposals.length !== 1 ? "s" : ""}
              </button>
            )}
            <button className="icon-btn" title="Settings">
              <Settings size={16} />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="master-content">
          {/* Chat window */}
          <div className={`master-chat-area${showProposals && pendingProposals.length > 0 ? " with-proposals" : ""}`}>
            {/* Empty state */}
            {!activeConvId && (
              <div className="master-empty-state">
                <div className="master-empty-icon">
                  <Bot size={48} />
                </div>
                <h2>Chat with AI Master</h2>
                <p>
                  Describe your trading strategy in plain language. Master will parse it,
                  check the registry, flag complications, and prepare a proposal for you to confirm.
                </p>
                <div className="master-empty-examples">
                  <p className="master-empty-examples-label">Try saying:</p>
                  <div className="master-example-chips">
                    {[
                      "Buy Nifty ATM call when 5-min close is above VWAP and RSI > 60",
                      "Exit all positions at 15:10 if loss exceeds 25%",
                      "Show me strategies using RSI indicator",
                    ].map((ex) => (
                      <button
                        key={ex}
                        className="master-example-chip"
                        onClick={() => { handleNewConversation().then(() => handleSend(ex)); }}
                      >
                        {ex}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  id="master-start-chat-btn"
                  className="btn-primary master-start-btn"
                  onClick={handleNewConversation}
                  disabled={createMutation.isPending}
                >
                  <Bot size={16} />
                  Start a New Chat
                </button>
              </div>
            )}

            {/* Messages */}
            {activeConvId && (
              <div className="master-messages">
                {messagesQuery.isLoading && (
                  <div className="master-messages-loading">Loading messages…</div>
                )}

                {messages.map((msg) => (
                  <MessageBubble
                    key={msg.id}
                    message={msg}
                    onChoice={handleChoice}
                  />
                ))}

                {/* Streaming delta */}
                {streamingContent && (
                  <MessageBubble
                    message={{
                      id: -1,
                      conversationId: activeConvId,
                      seq: 9999,
                      role: "assistant",
                      content: streamingContent,
                      redacted: false,
                      createdAt: new Date().toISOString(),
                    }}
                    isStreaming
                  />
                )}

                {/* Thinking indicator */}
                {thinkingEvent && !streamingContent && (
                  <ThinkingIndicator event={thinkingEvent.event} label={thinkingEvent.label} />
                )}

                {/* Run error */}
                {runState === "ERROR" && (
                  <div className="master-run-error">
                    ⚠ Master encountered an error. Please try again.
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            )}

            {/* Quick suggestions if conversation has few messages */}
            {activeConvId && messages.length <= 2 && !isRunning && (
              <div className="master-quick-suggestions">
                {[
                  "💡 What strategies are registered?",
                  "📈 Explain RSI and VWAP indicators",
                  "⚡ Buy Nifty ATM Call when close > VWAP and RSI > 60",
                  "🛡️ Set max daily portfolio loss to 2%",
                ].map((sug, i) => (
                  <button
                    key={i}
                    className="master-quick-chip"
                    onClick={() => handleSend(sug.replace(/^[^\w\s]+\s*/, ""))}
                  >
                    {sug}
                  </button>
                ))}
              </div>
            )}

            {/* Chat input */}
            {activeConvId && (
              <ChatInput
                onSend={handleSend}
                onCancel={handleCancelRun}
                isSending={sendMutation.isPending}
                isRunning={isRunning}
                disabled={false}
              />
            )}
          </div>

          {/* Proposals panel */}
          {showProposals && pendingProposals.length > 0 && (
            <div className="master-proposals-panel">
              <div className="master-proposals-header">
                <h3>Pending Proposals</h3>
                <button className="icon-btn" onClick={() => setShowProposals(false)}>✕</button>
              </div>
              <div className="master-proposals-list">
                {pendingProposals.map((p) => (
                  <ProposalCard
                    key={p.id}
                    proposal={p}
                    onConfirm={handleConfirm}
                    onReject={handleReject}
                    onRevalidate={handleRevalidate}
                    isConfirming={confirmMutation.isPending}
                    isRejecting={rejectMutation.isPending}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
