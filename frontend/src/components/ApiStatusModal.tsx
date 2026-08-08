'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { 
  ShieldCheck, 
  Cpu, 
  Database, 
  Search, 
  RefreshCw, 
  X, 
  CheckCircle2, 
  AlertCircle,
  Clock,
  Sparkles
} from 'lucide-react';
import { getApiUrl } from '@/lib/api';

interface ApiStatusData {
  connected: boolean;
  status: 'connected' | 'degraded' | 'error';
  checked_at: string;
  total_latency_ms: number;
  llm: {
    provider: string;
    model: string;
    connected: boolean;
    latency_ms: number;
    error?: string | null;
  };
  vector_store: {
    collection_name: string;
    total_chunks: number;
    status: string;
  };
  embeddings: {
    provider: string;
    model: string;
    ready: boolean;
  };
  tavily: {
    configured: boolean;
    status: string;
  };
}

interface ApiStatusModalProps {
  className?: string;
}

export default function ApiStatusModal({ className = '' }: ApiStatusModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [statusData, setStatusData] = useState<ApiStatusData | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  const checkStatus = async () => {
    setIsChecking(true);
    try {
      const res = await fetch(getApiUrl('/api/status'), {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data = await res.json();
        setStatusData(data);
        setLastChecked(new Date());
      } else {
        throw new Error(`Status check returned ${res.status}`);
      }
    } catch (err: any) {
      setStatusData({
        connected: false,
        status: 'error',
        checked_at: new Date().toISOString(),
        total_latency_ms: 0,
        llm: {
          provider: 'Groq',
          model: 'llama-3.3-70b-versatile',
          connected: false,
          latency_ms: 0,
          error: `Could not connect to backend server at ${getApiUrl('/api/status')}`,
        },
        vector_store: { collection_name: 'repo_docs', total_chunks: 0, status: 'unavailable' },
        embeddings: { provider: 'local', model: 'all-MiniLM-L6-v2', ready: false },
        tavily: { configured: false, status: 'unavailable' },
      });
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const isConnected = statusData?.connected ?? false;

  return (
    <>
      {/* Integrated Status Button */}
      <button
        onClick={() => setIsOpen(true)}
        className={`api-status-btn glass-panel ${
          isConnected ? 'connected' : isChecking ? 'checking' : 'disconnected'
        } ${className}`}
        title="Click to view API & Subsystems Connection Status"
      >
        <div className="status-led-wrapper">
          <span className={`led-indicator ${isConnected ? 'green-blink' : isChecking ? 'amber-pulse' : 'red-dot'}`} />
          {isConnected && <span className="led-ping-ring" />}
        </div>

        <span className="api-status-label">
          {isChecking
            ? 'Verifying API...'
            : isConnected
            ? 'API Connected'
            : 'API Offline'}
        </span>

        {isConnected && statusData?.llm?.latency_ms ? (
          <span className="api-latency-pill">{statusData.llm.latency_ms}ms</span>
        ) : null}
      </button>

      {/* Connection Detail Modal */}
      {isOpen && mounted && createPortal(
        <div className="modal-backdrop" onClick={() => setIsOpen(false)}>
          <div
            className="api-modal-card glass-panel"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="modal-header">
              <div className="modal-title-group">
                <div className="modal-icon-badge">
                  <ShieldCheck size={22} className="text-accent" />
                </div>
                <div>
                  <h3>API & Services Verification</h3>
                  <p className="modal-subtitle">Real-time telemetry and subsystem health</p>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  onClick={checkStatus}
                  disabled={isChecking}
                  className="refresh-status-btn"
                  title="Refresh status check"
                >
                  <RefreshCw size={14} className={isChecking ? 'spin' : ''} />
                  <span>{isChecking ? 'Testing...' : 'Re-test'}</span>
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="modal-close-btn"
                  title="Close"
                >
                  <X size={18} />
                </button>
              </div>
            </div>

            {/* Overall Status Banner */}
            <div className={`status-banner ${isConnected ? 'banner-connected' : 'banner-error'}`}>
              <div className="banner-left">
                {isConnected ? (
                  <div className="status-led-large">
                    <span className="led-indicator-large green-blink" />
                    <span className="led-ping-ring-large" />
                  </div>
                ) : (
                  <AlertCircle size={22} className="text-red-400" />
                )}
                <div>
                  <h4 className="banner-title">
                    {isConnected ? 'All Core Subsystems Operational' : 'Backend Connection Issue'}
                  </h4>
                  <p className="banner-desc">
                    {isConnected
                      ? `FastAPI server responding at sub-second speeds (${statusData?.total_latency_ms || 0}ms).`
                      : 'Ensure FastAPI backend is running on port 8000.'}
                  </p>
                </div>
              </div>
            </div>

            {/* 2x2 Services Grid */}
            <div className="services-grid">
              {/* Card 1: Groq LLM */}
              <div className="service-card">
                <div className="service-card-header">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <div className="service-icon">
                      <Cpu size={18} />
                    </div>
                    <span className="service-name">LLM Inference (Groq)</span>
                  </div>
                  <span className={`badge-pill ${statusData?.llm?.connected ? 'pill-success' : 'pill-danger'}`}>
                    {statusData?.llm?.connected ? 'Online' : 'Offline'}
                  </span>
                </div>

                <div className="service-details">
                  <div className="detail-row">
                    <span className="detail-key">Model:</span>
                    <span className="detail-val font-mono">{statusData?.llm?.model || 'llama-3.3-70b-versatile'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Provider:</span>
                    <span className="detail-val">{statusData?.llm?.provider || 'Groq'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Latency:</span>
                    <span className="detail-val font-mono">
                      {statusData?.llm?.latency_ms ? `${statusData.llm.latency_ms} ms` : 'N/A'}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">API Status:</span>
                    <span className="detail-val text-green-400">
                      {statusData?.llm?.connected ? 'Connected (Authenticated)' : 'Check GROQ_API_KEY'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Card 2: ChromaDB Vector Store */}
              <div className="service-card">
                <div className="service-card-header">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <div className="service-icon">
                      <Database size={18} className="text-amber-400" />
                    </div>
                    <span className="service-name">Vector Store (ChromaDB)</span>
                  </div>
                  <span className={`badge-pill ${statusData?.vector_store?.status === 'ready' ? 'pill-success' : 'pill-warning'}`}>
                    {statusData?.vector_store?.status === 'ready' ? 'Ready' : 'Initialized'}
                  </span>
                </div>

                <div className="service-details">
                  <div className="detail-row">
                    <span className="detail-key">Collection:</span>
                    <span className="detail-val font-mono">{statusData?.vector_store?.collection_name || 'repo_docs'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Indexed Chunks:</span>
                    <span className="detail-val font-mono text-accent" style={{ fontWeight: 600 }}>
                      {statusData?.vector_store?.total_chunks ?? 0}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Type:</span>
                    <span className="detail-val">Local Persistent Store</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Storage Path:</span>
                    <span className="detail-val font-mono">./chroma_db</span>
                  </div>
                </div>
              </div>

              {/* Card 3: Embeddings Model */}
              <div className="service-card">
                <div className="service-card-header">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <div className="service-icon">
                      <Sparkles size={18} className="text-purple-400" />
                    </div>
                    <span className="service-name">Embedding Engine</span>
                  </div>
                  <span className={`badge-pill ${statusData?.embeddings?.ready ? 'pill-success' : 'pill-danger'}`}>
                    {statusData?.embeddings?.ready ? 'Loaded' : 'Pending'}
                  </span>
                </div>

                <div className="service-details">
                  <div className="detail-row">
                    <span className="detail-key">Model:</span>
                    <span className="detail-val font-mono">{statusData?.embeddings?.model || 'all-MiniLM-L6-v2'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Dimensions:</span>
                    <span className="detail-val font-mono">384-dim</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Framework:</span>
                    <span className="detail-val">SentenceTransformers</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Cost:</span>
                    <span className="detail-val text-green-400">100% Free / Local</span>
                  </div>
                </div>
              </div>

              {/* Card 4: Web Search Fallback */}
              <div className="service-card">
                <div className="service-card-header">
                  <div style={{ display: 'flex', alignItems: 'center' }}>
                    <div className="service-icon">
                      <Search size={18} className="text-emerald-400" />
                    </div>
                    <span className="service-name">Web Fallback (Tavily)</span>
                  </div>
                  <span className={`badge-pill ${statusData?.tavily?.configured ? 'pill-success' : 'pill-secondary'}`}>
                    {statusData?.tavily?.configured ? 'Active' : 'Optional'}
                  </span>
                </div>

                <div className="service-details">
                  <div className="detail-row">
                    <span className="detail-key">API Key:</span>
                    <span className="detail-val">
                      {statusData?.tavily?.configured ? 'Configured' : 'Not Set (Optional)'}
                    </span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Role:</span>
                    <span className="detail-val">Agent Fallback Grounding</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Status:</span>
                    <span className="detail-val font-mono">{statusData?.tavily?.status || 'available'}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-key">Trigger:</span>
                    <span className="detail-val">Low retrieval confidence</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="modal-footer">
              {lastChecked ? (
                <div className="footer-timestamp">
                  <Clock size={13} />
                  <span>Last checked at {lastChecked.toLocaleTimeString()}</span>
                </div>
              ) : (
                <span className="footer-timestamp">Telemetry synced</span>
              )}
              <button onClick={() => setIsOpen(false)} className="modal-done-btn">
                Close
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
