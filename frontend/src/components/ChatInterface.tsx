'use client';

import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Bot, 
  User, 
  ArrowRight, 
  ExternalLink, 
  FileCode, 
  BookOpen, 
  Settings2, 
  Layers, 
  Sparkles, 
  ChevronRight
} from 'lucide-react';
import ApiStatusModal from './ApiStatusModal';
import { 
  ChatMessage, 
  ChatSession, 
  getStoredSessions, 
  getSessionById, 
  saveSessionMessages, 
  createNewSession 
} from '@/lib/chatSessionStorage';
import { getApiUrl } from '@/lib/api';

interface ChatInterfaceProps {
  activeRepo: string;
  currentSessionId?: string | null;
  onSelectSession?: (sessionId: string) => void;
  onSessionsChange?: (sessions: ChatSession[]) => void;
  onOpenHistory?: () => void;
  onNewChat?: () => void;
}

export default function ChatInterface({ 
  activeRepo, 
  currentSessionId, 
  onSelectSession,
  onSessionsChange,
  onOpenHistory,
  onNewChat
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(currentSessionId || null);
  const [sessionTitle, setSessionTitle] = useState<string>('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const repoDisplayName = activeRepo.replace(/\/+$/, '').split('/').pop()?.replace('.git', '') || activeRepo;

  const samplePrompts = [
    'Explain the full repository architecture & directory structure',
    'Where is the main entry point and how does the data flow work?',
    'What are the core classes/modules and how do they interact?',
    'How do I install dependencies and run this project locally?',
  ];

  // Synchronize active session when currentSessionId or activeRepo changes
  useEffect(() => {
    const allSessions = getStoredSessions();
    let targetSession: ChatSession | null = null;

    if (currentSessionId) {
      targetSession = getSessionById(currentSessionId);
    }

    if (!targetSession) {
      // Find the most recent session for this specific repo
      const forRepo = allSessions.filter((s) => s.repoUrl === activeRepo);
      if (forRepo.length > 0) {
        targetSession = forRepo.sort(
          (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        )[0];
      }
    }

    if (targetSession) {
      setActiveSessionId(targetSession.id);
      setSessionTitle(targetSession.title);
      setMessages(targetSession.messages || []);
    } else {
      // Create a clean initial session
      const created = createNewSession(activeRepo);
      setActiveSessionId(created.id);
      setSessionTitle(created.title);
      setMessages([]);
      onSessionsChange?.(getStoredSessions());
    }
  }, [activeRepo, currentSessionId]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const sendQuestion = async (query: string) => {
    const cleanQuery = query.trim();
    if (!cleanQuery || isLoading) return;

    // Ensure we have an active session id
    let sessionId = activeSessionId;
    if (!sessionId) {
      const created = createNewSession(activeRepo);
      sessionId = created.id;
      setActiveSessionId(sessionId);
      setSessionTitle(created.title);
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: cleanQuery,
    };

    const messagesWithUser = [...messages, userMessage];
    setMessages(messagesWithUser);
    setInput('');
    setIsLoading(true);

    // Save immediately so state is preserved even if user navigates or reloads
    const updatedWithUser = saveSessionMessages(sessionId, messagesWithUser, activeRepo);
    onSessionsChange?.(updatedWithUser);

    // Build multi-turn history payload (last 6 messages for context)
    const historyPayload = messages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const res = await fetch(getApiUrl('/ask'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          question: userMessage.content, 
          repo_url: activeRepo,
          session_id: sessionId,
          history: historyPayload
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Failed to retrieve codebase answer');
      }

      const agentMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: data.answer,
        citations: data.citations || [],
        confidence: data.confidence,
      };

      const messagesWithAgent = [...messagesWithUser, agentMessage];
      setMessages(messagesWithAgent);

      // Persist full exchange to localStorage
      const updatedWithAgent = saveSessionMessages(sessionId, messagesWithAgent, activeRepo);
      onSessionsChange?.(updatedWithAgent);

      // Update local session title if first turn
      const updatedCurrent = updatedWithAgent.find((s) => s.id === sessionId);
      if (updatedCurrent) {
        setSessionTitle(updatedCurrent.title);
      }
    } catch (error: any) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: `**Error communicating with agent**: ${error.message}\n\n*Please ensure the backend server is running and the repository has been indexed.*`,
      };
      const messagesWithError = [...messagesWithUser, errorMessage];
      setMessages(messagesWithError);
      const updatedWithError = saveSessionMessages(sessionId, messagesWithError, activeRepo);
      onSessionsChange?.(updatedWithError);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sendQuestion(input);
  };

  const getSourceIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'architecture':
        return <Layers size={12} className="text-amber-400" />;
      case 'code':
        return <FileCode size={12} className="text-blue-400" />;
      case 'configuration':
        return <Settings2 size={12} className="text-purple-400" />;
      default:
        return <BookOpen size={12} className="text-emerald-400" />;
    }
  };

  const renderConfidence = (score?: number) => {
    if (score === undefined) return null;
    let label = 'Low Confidence';
    let dotClass = 'dot-red';
    let badgeClass = 'confidence-low';

    if (score >= 0.8) {
      label = 'High Confidence';
      dotClass = 'dot-green';
      badgeClass = 'confidence-high';
    } else if (score >= 0.5) {
      label = 'Medium Confidence';
      dotClass = 'dot-yellow';
      badgeClass = 'confidence-med';
    }

    return (
      <div className={`confidence-badge ${badgeClass}`}>
        <span className={`confidence-dot ${dotClass}`} />
        <span>{label} ({Math.round(score * 100)}%)</span>
      </div>
    );
  };

  return (
    <div className="chat-container">
      {/* Top Header Bar for Active Repository and Integrated API Status */}
      <div className="chat-header glass-panel">
        <div className="repo-badge">
          <span className="label">Active Repository:</span>
          <span className="value font-mono">{repoDisplayName}</span>
          <a
            href={activeRepo.startsWith('http') ? activeRepo : `https://${activeRepo}`}
            target="_blank"
            rel="noreferrer"
            className="repo-external-link"
            title="Open on GitHub"
          >
            <ExternalLink size={13} />
          </a>
        </div>

        {/* Seamlessly Integrated API Status Button */}
        <div className="chat-header-right">
          <ApiStatusModal />
        </div>
      </div>

      {/* Messages area */}
      <div className="chat-history">
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-icon-glow">
              <Sparkles size={28} />
            </div>
            <h3>Ask Deep Questions About {repoDisplayName}</h3>
            <p>
              I can analyze the entire codebase, file relationships, architectures, functions,
              configs, and documentation.
            </p>

            <div className="prompt-suggestions">
              <span className="suggestions-label">Try asking:</span>
              <div className="prompt-chips">
                {samplePrompts.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendQuestion(prompt)}
                    className="prompt-chip glass-panel"
                  >
                    <span>{prompt}</span>
                    <ChevronRight size={14} className="chip-arrow" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`message-wrapper ${msg.role}`}>
              <div className="avatar">
                {msg.role === 'agent' ? <Bot size={18} /> : <User size={18} />}
              </div>

              <div className="message-content">
                <div className={`bubble glass-panel ${msg.role}`}>
                  <div className="markdown-body">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>

                  {((msg.citations && msg.citations.length > 0) || (msg.role === 'agent' && msg.confidence !== undefined)) && (
                    <div className="bubble-meta-footer">
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="citations-group">
                          <div className="citation-label">
                            <BookOpen size={12} className="citation-label-icon" />
                            <span>Referenced Sources ({msg.citations.length})</span>
                          </div>
                          <div className="citation-chips">
                            {msg.citations.map((c, i) => (
                              <div key={i} className="citation-link" title={`Source: ${c.source}`}>
                                {getSourceIcon(c.type)}
                                <span className="citation-source-name">{c.source}</span>
                                {c.lines ? (
                                  <span className="citation-lines">L{c.lines}</span>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {msg.role === 'agent' && (
                        <div className="confidence-wrapper">
                          {renderConfidence(msg.confidence)}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="message-wrapper agent">
            <div className="avatar">
              <Bot size={18} className="animate-pulse" />
            </div>
            <div className="message-content">
              <div className="bubble glass-panel agent typing-bubble">
                <div className="typing-indicator">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
                <span className="typing-text">
                  Analyzing architecture, retrieving code chunks & synthesizing answer...
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-area">
        <form onSubmit={handleSubmit} className="input-form">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask any question about ${repoDisplayName} (e.g. architecture, functions, configs, bugs)...`}
            disabled={isLoading}
            className="chat-input"
            autoFocus
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="send-btn"
            title="Send query"
          >
            <ArrowRight size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
