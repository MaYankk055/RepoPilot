'use client';

import { useState, useEffect, useCallback } from 'react';
import RepoIngester from '@/components/RepoIngester';
import ChatInterface from '@/components/ChatInterface';
import ApiStatusModal from '@/components/ApiStatusModal';
import ChatHistoryModal, { ChatSession } from '@/components/ChatHistoryModal';
import { 
  getStoredSessions, 
  deleteStoredSession, 
  clearAllStoredSessions, 
  createNewSession 
} from '@/lib/chatSessionStorage';
import { GitBranch, Layers, Sparkles, Terminal, History, Plus, MessageSquare } from 'lucide-react';

export default function Home() {
  const [activeRepo, setActiveRepo] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Initial sync from localStorage
  useEffect(() => {
    setSessions(getStoredSessions());
  }, [isHistoryOpen, activeRepo]);

  const sampleRepos = [
    { name: 'Propwise', url: 'https://github.com/MaYankk055/Propwise.git' },
    { name: 'LangChain', url: 'https://github.com/langchain-ai/langchain.git' },
    { name: 'FastAPI', url: 'https://github.com/tiangolo/fastapi.git' },
  ];

  const handleSelectSession = useCallback((sessionId: string) => {
    const freshSessions = getStoredSessions();
    const found = freshSessions.find((s) => s.id === sessionId);
    if (found) {
      setActiveRepo(found.repoUrl);
      setCurrentSessionId(found.id);
      setSessions(freshSessions);
      setIsHistoryOpen(false);
    }
  }, []);

  const handleNewChat = useCallback(() => {
    if (activeRepo) {
      const created = createNewSession(activeRepo);
      const updated = getStoredSessions();
      setSessions(updated);
      setCurrentSessionId(created.id);
      setIsHistoryOpen(false);
    } else {
      setActiveRepo(null);
      setCurrentSessionId(null);
      setIsHistoryOpen(false);
    }
  }, [activeRepo]);

  const handleDeleteSession = useCallback((sessionId: string) => {
    const updated = deleteStoredSession(sessionId);
    setSessions(updated);

    if (currentSessionId === sessionId) {
      if (updated.length > 0) {
        handleSelectSession(updated[0].id);
      } else {
        setCurrentSessionId(null);
      }
    }
  }, [currentSessionId, handleSelectSession]);

  const handleClearAll = useCallback(() => {
    clearAllStoredSessions();
    setSessions([]);
    setCurrentSessionId(null);
  }, []);

  return (
    <div className="layout-container">
      {/* Sidebar */}
      <aside className="sidebar glass-panel">
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon-wrapper">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </div>
            <div>
              <h1>RepoPilot</h1>
              <p className="subtitle">Deep Codebase Intelligence RAG</p>
            </div>
          </div>
        </div>

        {/* Sidebar Actions: New Chat & Previous Chats */}
        <div className="sidebar-nav-actions">
          <button
            onClick={handleNewChat}
            className="sidebar-nav-btn new-chat-btn glass-panel"
            title="Start a new chat session"
          >
            <div className="nav-btn-content">
              <Plus size={16} className="nav-btn-icon" />
              <span className="nav-btn-label">New Chat</span>
            </div>
          </button>

          <button
            onClick={() => setIsHistoryOpen(true)}
            className="sidebar-nav-btn history-btn glass-panel"
            title="View previous chat sessions"
          >
            <div className="nav-btn-content">
              <History size={16} className="nav-btn-icon" />
              <span className="nav-btn-label">Previous Chats</span>
            </div>
            {sessions.length > 0 && (
              <span className="nav-btn-pill">{sessions.length}</span>
            )}
          </button>
        </div>
        
        <div className="sidebar-content">
          <RepoIngester 
            onIngestSuccess={(repo) => {
              setActiveRepo(repo);
              setCurrentSessionId(null);
            }} 
            activeRepo={activeRepo}
          />
        </div>
        
        <div className="sidebar-footer">
          <div className="sidebar-target-card glass-panel">
            <div className="target-card-header">
              <div className="target-status-led">
                <span className={`status-dot-pulse ${activeRepo ? 'active' : 'idle'}`} />
                {activeRepo && <span className="status-ping-ring" />}
              </div>
              <span className="target-status-label">
                {activeRepo ? 'ACTIVE REPO' : 'WORKSPACE STATUS'}
              </span>
            </div>
            <div className="target-repo-info">
              <GitBranch size={13} className={activeRepo ? 'text-accent' : 'text-muted'} />
              <span className="target-repo-name truncate">
                {activeRepo ? activeRepo.split('/').pop()?.replace('.git', '') : 'No repo loaded'}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {activeRepo ? (
          <ChatInterface 
            activeRepo={activeRepo} 
            currentSessionId={currentSessionId}
            onSelectSession={handleSelectSession}
            onSessionsChange={(updated) => setSessions(updated)}
            onOpenHistory={() => setIsHistoryOpen(true)}
            onNewChat={handleNewChat}
          />
        ) : (
          <div className="empty-state-wrapper">
            {/* Top Bar for Empty State */}
            <div className="empty-state-topbar">
              <div className="app-breadcrumb">
                <span className="text-muted">Repository</span>
                <span className="text-muted">/</span>
                <span className="text-primary font-medium">Select Target</span>
              </div>
              <ApiStatusModal />
            </div>

            <div className="empty-state">
              <div className="empty-icon-card glass-panel">
                <Layers size={42} className="empty-icon text-accent" />
              </div>
              <h2>Full Codebase Intelligence</h2>
              <p>
                Index any public GitHub repository to analyze the complete architecture, source files, 
                modules, configurations, and documentation.
              </p>

              <div className="feature-highlights">
                <div className="highlight-pill glass-panel">
                  <GitBranch size={14} />
                  <span>Deep Multi-File Code Search</span>
                </div>
                <div className="highlight-pill glass-panel">
                  <Terminal size={14} />
                  <span>Architecture & Directory Mapping</span>
                </div>
                <div className="highlight-pill glass-panel">
                  <Sparkles size={14} />
                  <span>Contextual Code Answers</span>
                </div>
              </div>

              {sessions.length > 0 && (
                <div className="saved-chats-quick-access glass-panel">
                  <div className="saved-chats-header">
                    <div className="saved-chats-title-group">
                      <MessageSquare size={16} className="text-accent" />
                      <span>Saved Chat History ({sessions.length})</span>
                    </div>
                    <button
                      onClick={() => setIsHistoryOpen(true)}
                      className="view-all-history-btn"
                    >
                      View All
                    </button>
                  </div>
                  <div className="saved-chats-mini-list">
                    {sessions.slice(0, 3).map((s) => (
                      <button
                        key={s.id}
                        onClick={() => handleSelectSession(s.id)}
                        className="saved-chat-mini-item"
                      >
                        <span className="mini-item-repo">{s.repoName}</span>
                        <span className="mini-item-title truncate">{s.title}</span>
                        <span className="mini-item-msgs">{s.messages.length} msgs</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="quick-start-section">
                <span className="quick-start-title">Quick Try Public Repositories:</span>
                <div className="quick-repo-buttons">
                  {sampleRepos.map((repo) => (
                    <button
                      key={repo.url}
                      onClick={() => {
                        setActiveRepo(repo.url);
                        setCurrentSessionId(null);
                      }}
                      className="quick-repo-btn glass-panel"
                    >
                      {repo.name}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Global Previous Chat History Modal */}
      <ChatHistoryModal
        isOpen={isHistoryOpen}
        onClose={() => setIsHistoryOpen(false)}
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onDeleteSession={handleDeleteSession}
        onClearAll={handleClearAll}
      />
    </div>
  );
}
