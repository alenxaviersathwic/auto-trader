import React, { useRef, useState } from "react";
import { Send, StopCircle } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  onCancel?: () => void;
  isSending?: boolean;
  isRunning?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<Props> = ({
  onSend,
  onCancel,
  isSending,
  isRunning,
  disabled,
  placeholder = "Type your strategy or ask Master anything…",
}) => {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const text = value.trim();
    if (!text || isSending || disabled) return;
    onSend(text);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
    }
  };

  return (
    <div className="chat-input-container">
      <div className={`chat-input-box${disabled ? " disabled" : ""}`}>
        <textarea
          id="master-chat-input"
          ref={textareaRef}
          className="chat-textarea"
          placeholder={placeholder}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          rows={1}
          disabled={disabled || isSending}
        />
        <div className="chat-input-actions">
          {isRunning && onCancel && (
            <button
              id="master-cancel-run-btn"
              className="chat-cancel-btn"
              onClick={onCancel}
              title="Cancel run"
            >
              <StopCircle size={18} />
            </button>
          )}
          <button
            id="master-send-btn"
            className="chat-send-btn"
            onClick={handleSend}
            disabled={!value.trim() || isSending || disabled}
            title="Send message (Enter)"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
      <p className="chat-input-hint">
        Press <kbd>Enter</kbd> to send · <kbd>Shift+Enter</kbd> for newline
      </p>
    </div>
  );
};
