import React, { useState } from "react";
import { Conversation } from "../types/master.types";
import { PageResult } from "../../../core/types/pagination.types";
import {
  MessageSquare, Plus, Trash2, Edit3, Check, X, Archive, Search
} from "lucide-react";

interface Props {
  data?: PageResult<Conversation>;
  activeId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
  onRename: (id: number, title: string) => void;
  isCreating?: boolean;
}

export const ConversationSidebar: React.FC<Props> = ({
  data,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onRename,
  isCreating,
}) => {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [search, setSearch] = useState("");

  const conversations = (data?.list ?? []).filter((c) =>
    c.title.toLowerCase().includes(search.toLowerCase())
  );

  const startEdit = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const commitEdit = (id: number) => {
    if (editTitle.trim()) onRename(id, editTitle.trim());
    setEditingId(null);
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return "just now";
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    return d.toLocaleDateString();
  };

  return (
    <aside className="master-sidebar">
      <div className="master-sidebar-header">
        <span className="master-sidebar-title">Conversations</span>
        <button
          id="master-new-conversation-btn"
          className="master-new-btn"
          onClick={onNew}
          disabled={isCreating}
          title="New conversation"
        >
          <Plus size={16} />
        </button>
      </div>

      <div className="master-sidebar-search">
        <Search size={13} className="master-search-icon" />
        <input
          id="master-conversation-search"
          className="master-search-input"
          placeholder="Search conversations…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="master-sidebar-list">
        {conversations.length === 0 && (
          <div className="master-sidebar-empty">
            <MessageSquare size={28} />
            <p>No conversations yet</p>
            <p className="text-xs text-muted">Click + to start chatting with Master</p>
          </div>
        )}

        {conversations.map((c) => (
          <div
            key={c.id}
            id={`master-conv-${c.id}`}
            className={`master-conv-item${activeId === c.id ? " active" : ""}`}
            onClick={() => onSelect(c.id)}
          >
            <div className="master-conv-icon">
              {c.archived ? <Archive size={14} /> : <MessageSquare size={14} />}
            </div>

            <div className="master-conv-body">
              {editingId === c.id ? (
                <div className="master-conv-edit" onClick={(e) => e.stopPropagation()}>
                  <input
                    autoFocus
                    className="master-conv-edit-input"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitEdit(c.id);
                      if (e.key === "Escape") setEditingId(null);
                    }}
                  />
                  <button className="icon-btn success" onClick={() => commitEdit(c.id)}><Check size={12} /></button>
                  <button className="icon-btn danger" onClick={() => setEditingId(null)}><X size={12} /></button>
                </div>
              ) : (
                <>
                  <span className="master-conv-title">{c.title}</span>
                  <span className="master-conv-meta">
                    {c.messageCount} msg · {formatTime(c.lastMessageAt)}
                  </span>
                </>
              )}
            </div>

            {editingId !== c.id && (
              <div className="master-conv-actions">
                <button
                  className="icon-btn"
                  onClick={(e) => startEdit(c, e)}
                  title="Rename"
                >
                  <Edit3 size={12} />
                </button>
                <button
                  className="icon-btn danger"
                  onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
};
