'use client';

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { 
  History, 
  X, 
  MessageSquare, 
  Trash2, 
  Clock, 
  Download, 
  Plus, 
  Search, 
  GitBranch,
  ArrowRight
} from 'lucide-react';

import { ChatSession } from '@/lib/chatSessionStorage';
export type { ChatSession };

interface ChatHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  sessions: ChatSession[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  onClearAll: () => void;
}

export default function ChatHistoryModal({
  isOpen,
  onClose,
  sessions,
  currentSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onClearAll,
}: ChatHistoryModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !mounted) return null;

  const filteredSessions = sessions.filter((s) => {
    const term = searchTerm.toLowerCase();
    return (
      s.title.toLowerCase().includes(term) ||
      s.repoName.toLowerCase().includes(term) ||
      s.messages.some((m) => m.content.toLowerCase().includes(term))
    );
  });

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Recent';
    }
  };

  const cleanPreview = (text: string) => {
    if (!text) return '';
    return text
      .replace(/#{1,6}\s+/g, '') // remove markdown headers
      .replace(/\*\*(.*?)\*\*/g, '$1') // remove bold
      .replace(/\*(.*?)\*/g, '$1') // remove italics
      .replace(/`{1,3}[^`]*`{1,3}/g, '') // remove code blocks
      .replace(/\[(.*?)\]\(.*?\)/g, '$1') // remove links
      .replace(/>\s+/g, '') // remove blockquotes
      .replace(/\s+/g, ' ') // collapse whitespaces
      .trim();
  };

  const handleExportSession = (session: ChatSession, e: React.MouseEvent) => {
    e.stopPropagation();
    const markdownContent = `# RepoPilot Chat Session: ${session.title}\n**Repository:** ${session.repoUrl}\n**Date:** ${new Date(session.createdAt).toLocaleString()}\n\n---\n\n` +
      session.messages
        .map((m) => `### ${m.role === 'user' ? '👤 User' : '🤖 RepoPilot'}\n\n${m.content}\n\n${m.confidence ? `*Confidence: ${Math.round(m.confidence * 100)}%*\n\n` : ''}`)
        .join('\n---\n\n');

    const blob = new Blob([markdownContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `repopilot-chat-${session.repoName}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return createPortal(
    <div className="history-modal-overlay" onClick={onClose}>
      <div 
        className="history-modal-container glass-panel"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="history-modal-header">
          <div className="history-modal-title">
            <div className="history-icon-badge">
              <History size={18} className="text-accent" />
            </div>
            <div>
              <h3>Previous Chat History</h3>
              <p className="history-modal-subtitle">
                Browse, restore, or export past analysis conversations ({sessions.length} saved)
              </p>
            </div>
          </div>

          <div className="history-header-actions">
            <button
              onClick={() => {
                onNewChat();
                onClose();
              }}
              className="new-chat-action-btn"
              title="Start a fresh conversation"
            >
              <Plus size={14} />
              <span>New Chat</span>
            </button>
            <button 
              onClick={onClose} 
              className="history-close-btn" 
              title="Close modal (Esc)"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Search Filter Bar */}
        <div className="history-search-bar">
          <Search size={15} className="history-search-icon" />
          <input
            type="text"
            placeholder="Search saved conversations by title, repository, or message content..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="history-search-input"
            autoFocus
          />
          {searchTerm && (
            <button 
              onClick={() => setSearchTerm('')}
              className="history-search-clear"
              title="Clear search filter"
            >
              <X size={13} />
            </button>
          )}
        </div>

        {/* Sessions List */}
        <div className="history-sessions-list">
          {filteredSessions.length === 0 ? (
            <div className="history-empty-state">
              <div className="empty-state-icon-box">
                <MessageSquare size={32} />
              </div>
              <h4>{searchTerm ? 'No matching chats found' : 'No saved conversations yet'}</h4>
              <p>
                {searchTerm 
                  ? `No conversations match "${searchTerm}". Try searching for other terms or repo names.` 
                  : 'Start asking questions to build your codebase intelligence chat history.'}
              </p>
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="history-reset-search-btn"
                >
                  Clear Search Filter
                </button>
              )}
            </div>
          ) : (
            filteredSessions.map((session) => {
              const isSelected = session.id === currentSessionId;
              const previewText = session.messages.length > 0
                ? cleanPreview(session.messages[session.messages.length - 1].content)
                : '';

              return (
                <div
                  key={session.id}
                  onClick={() => {
                    onSelectSession(session.id);
                    onClose();
                  }}
                  className={`history-session-card ${isSelected ? 'active-session' : ''}`}
                >
                  {/* Card Header */}
                  <div className="session-card-header">
                    <div className="session-tags-group">
                      <div className="session-repo-badge">
                        <GitBranch size={11} className="repo-badge-icon" />
                        <span className="session-repo-name">{session.repoName}</span>
                      </div>
                      {isSelected && (
                        <span className="session-active-pill">
                          <span className="active-dot" />
                          Current Chat
                        </span>
                      )}
                    </div>

                    <div className="session-header-right">
                      <span className="session-timestamp">
                        <Clock size={11} />
                        <span>{formatDate(session.updatedAt || session.createdAt)}</span>
                      </span>

                      <div className="session-card-actions" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={(e) => handleExportSession(session, e)}
                          className="session-action-btn export-btn"
                          title="Export conversation as Markdown"
                        >
                          <Download size={13} />
                        </button>
                        
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (window.confirm(`Delete conversation "${session.title}"?`)) {
                              onDeleteSession(session.id);
                            }
                          }}
                          className="session-action-btn delete-btn"
                          title="Delete conversation"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Card Title */}
                  <h4 className="session-card-title">{session.title}</h4>

                  {/* Clean Preview Snippet */}
                  {previewText ? (
                    <p className="session-card-snippet">{previewText}</p>
                  ) : (
                    <p className="session-card-snippet empty-snippet">Empty conversation</p>
                  )}

                  {/* Card Footer */}
                  <div className="session-card-footer">
                    <span className="session-msg-badge">
                      <MessageSquare size={11} />
                      <span>{session.messages.length} message{session.messages.length === 1 ? '' : 's'}</span>
                    </span>

                    <span className="session-open-hint">
                      <span>Open chat</span>
                      <ArrowRight size={11} />
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer with Clear All */}
        {sessions.length > 0 && (
          <div className="history-modal-footer">
            <span className="history-footer-count">
              Showing <strong className="highlight-count">{filteredSessions.length}</strong> of {sessions.length} saved chats
            </span>
            <button
              onClick={() => {
                if (window.confirm('Are you sure you want to delete all saved chat history? This cannot be undone.')) {
                  onClearAll();
                }
              }}
              className="history-clear-all-btn"
            >
              <Trash2 size={13} />
              <span>Clear All History</span>
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
