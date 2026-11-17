import React from "react";
import { Message, MessageBlock } from "../types/master.types";
import { Bot, User, Wrench, AlertTriangle, CheckCircle2, Clock, Sparkles } from "lucide-react";

interface Props {
  message: Message;
  isStreaming?: boolean;
}

function renderInline(text: string): React.ReactNode {
  const tokens = text.split(/(\*\*.*?\*\*|`.*?`)/g);
  return tokens.map((t, i) => {
    if (t.startsWith("**") && t.endsWith("**")) {
      return <strong key={i} className="md-bold">{t.slice(2, -2)}</strong>;
    }
    if (t.startsWith("`") && t.endsWith("`")) {
      return <code key={i} className="md-code">{t.slice(1, -1)}</code>;
    }
    return t;
  });
}

function FormattedContent({ content }: { content: string }) {
  const parts = content.split(/(```[\s\S]*?```)/g);

  return (
    <div className="formatted-markdown">
      {parts.map((part, idx) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const lines = part.slice(3, -3).trim().split("\n");
          const lang = lines[0].match(/^[a-zA-Z0-9_-]+$/) ? lines[0] : "";
          const code = lang ? lines.slice(1).join("\n") : lines.join("\n");
          return (
            <div key={idx} className="code-block-wrapper">
              {lang && <div className="code-block-header">{lang}</div>}
              <pre className="code-block"><code>{code}</code></pre>
            </div>
          );
        }

        return (
          <div key={idx} className="markdown-text-chunk">
            {part.split("\n\n").map((para, pIdx) => {
              const trimmed = para.trim();
              if (!trimmed) return null;

              if (trimmed.startsWith("### ")) {
                return <h4 key={pIdx} className="md-h4">{renderInline(trimmed.slice(4))}</h4>;
              }
              if (trimmed.startsWith("## ")) {
                return <h3 key={pIdx} className="md-h3">{renderInline(trimmed.slice(3))}</h3>;
              }
              if (trimmed.startsWith("# ")) {
                return <h2 key={pIdx} className="md-h2">{renderInline(trimmed.slice(2))}</h2>;
              }

              const lines = trimmed.split("\n");
              const isList = lines.length > 1 && lines.every(
                (l) => l.trim().startsWith("- ") || l.trim().startsWith("* ") || /^\d+\.\s/.test(l.trim())
              );

              if (isList) {
                return (
                  <ul key={pIdx} className="md-list">
                    {lines.map((l, lIdx) => {
                      const itemText = l.replace(/^[-*]\s+|\d+\.\s+/, "");
                      return <li key={lIdx}>{renderInline(itemText)}</li>;
                    })}
                  </ul>
                );
              }

              return (
                <p key={pIdx} className="md-p">
                  {lines.map((l, lIdx) => (
                    <React.Fragment key={lIdx}>
                      {renderInline(l)}
                      {lIdx < lines.length - 1 && <br />}
                    </React.Fragment>
                  ))}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

function ComplicationBadge({ block }: { block: MessageBlock }) {
  const sev = (block.severity as string) || "INFO";
  const cls = sev === "BLOCKER" ? "complication-blocker" : sev === "WARNING" ? "complication-warning" : "complication-info";
  return (
    <div className={`complication-badge ${cls}`}>
      <AlertTriangle size={12} />
      <span>{block.message as string}</span>
    </div>
  );
}

function ProposalRefBlock({ block }: { block: MessageBlock }) {
  return (
    <div className="proposal-ref-block">
      <CheckCircle2 size={14} className="text-success" />
      <span>Proposal #{block.proposalId as number} — {block.kind as string}</span>
    </div>
  );
}

function ToolCallBlock({ block }: { block: MessageBlock }) {
  return (
    <div className="tool-call-block">
      <Wrench size={12} />
      <span className="tool-call-name">{block.toolName as string}</span>
      <span className="tool-call-tier">{block.tier as string}</span>
    </div>
  );
}

function ChoiceBlock({ block, onChoice }: { block: MessageBlock; onChoice?: (choice: string) => void }) {
  const choices = (block.choices as string[]) || [];
  return (
    <div className="choice-block">
      {choices.map((c) => (
        <button key={c} className="choice-btn" onClick={() => onChoice?.(c)}>
          {c}
        </button>
      ))}
    </div>
  );
}

export const MessageBubble: React.FC<Props & { onChoice?: (choice: string) => void }> = ({
  message,
  isStreaming,
  onChoice,
}) => {
  const roleStr = (message.role || "").toLowerCase();
  const isUser = roleStr === "user";
  const isTool = roleStr === "tool";

  if (isTool) {
    return (
      <div className="msg-tool-row">
        <Wrench size={12} />
        <span className="msg-tool-text">{message.content}</span>
      </div>
    );
  }

  return (
    <div className={`msg-row ${isUser ? "msg-row--user" : "msg-row--assistant"}`}>
      <div className={`msg-avatar ${isUser ? "msg-avatar--user" : "msg-avatar--ai"}`}>
        {isUser ? <User size={15} /> : <Bot size={15} />}
        {!isUser && <span className="ai-status-dot" />}
      </div>
      <div className="msg-content">
        <div className={`msg-bubble ${isUser ? "msg-bubble--user" : "msg-bubble--ai"}`}>
          <div className="msg-text">
            {isUser ? (
              <span>{message.content}</span>
            ) : (
              <FormattedContent content={message.content} />
            )}
            {isStreaming && <span className="typing-cursor">|</span>}
          </div>
          {(message.blocks ?? []).map((block, i) => {
            switch (block.type) {
              case "complication": return <ComplicationBadge key={i} block={block} />;
              case "proposal_ref": return <ProposalRefBlock key={i} block={block} />;
              case "tool_call": return <ToolCallBlock key={i} block={block} />;
              case "choice": return <ChoiceBlock key={i} block={block} onChoice={onChoice} />;
              default: return null;
            }
          })}
        </div>
        <div className="msg-footer">
          {message.model && (
            <span className="msg-model">
              <Sparkles size={10} /> {message.model}
            </span>
          )}
          {message.latencyMs && (
            <span className="msg-latency">
              <Clock size={10} /> {message.latencyMs}ms
            </span>
          )}
          <span className="msg-time">{new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
        </div>
      </div>
    </div>
  );
};
