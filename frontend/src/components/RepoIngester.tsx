'use client';

import { useState } from 'react';
import { Database, GitBranch, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';
import { getApiUrl } from '@/lib/api';

interface RepoIngesterProps {
  onIngestSuccess: (repoUrl: string) => void;
  activeRepo?: string | null;
}

export default function RepoIngester({ onIngestSuccess, activeRepo }: RepoIngesterProps) {
  const [repoUrl, setRepoUrl] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [successInfo, setSuccessInfo] = useState<{ repo: string; chunks: number } | null>(null);

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrl) return;

    setIsIngesting(true);
    setError(null);
    setSuccessInfo(null);
    setIngestStatus('Cloning repository & analyzing architecture...');

    try {
      // Periodic status message updates for better UX
      const statusTimer = setTimeout(() => {
        setIngestStatus('Parsing codebase, functions & dependencies...');
      }, 4000);

      const statusTimer2 = setTimeout(() => {
        setIngestStatus('Chunking code & embedding into Chroma vector store...');
      }, 9000);

      const res = await fetch(getApiUrl('/ingest'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ repo_url: repoUrl.trim() }),
      });

      clearTimeout(statusTimer);
      clearTimeout(statusTimer2);

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || 'Ingestion failed');
      }

      setSuccessInfo({
        repo: data.repo,
        chunks: data.chunks_stored,
      });

      onIngestSuccess(repoUrl.trim());
      setRepoUrl('');
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred during ingestion.');
    } finally {
      setIsIngesting(false);
      setIngestStatus('');
    }
  };

  return (
    <div className="ingester-container">
      <div className="ingester-title-group">
        <GitBranch size={16} className="text-accent" />
        <h3>Ingest Repository</h3>
      </div>
      <p className="description">
        Provide any public GitHub URL to clone, extract architecture maps, chunk source code, and index deep vectors.
      </p>

      <form onSubmit={handleIngest} className="ingest-form">
        <div className="input-group">
          <input
            type="text"
            placeholder="https://github.com/owner/repo.git"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={isIngesting}
            required
            className="glass-input"
          />
        </div>

        {isIngesting && (
          <div className="ingestion-progress glass-panel">
            <RefreshCw size={14} className="spin text-accent" />
            <span>{ingestStatus}</span>
          </div>
        )}

        {error && (
          <div className="error-message">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {successInfo && (
          <div className="success-message">
            <CheckCircle size={14} className="text-success" />
            <span>Indexed {successInfo.chunks} codebase chunks!</span>
          </div>
        )}

        <button 
          type="submit" 
          disabled={isIngesting || !repoUrl}
          className="submit-btn"
        >
          {isIngesting ? (
            <span className="loading-content">
              <span className="spinner"></span>
              Indexing Codebase...
            </span>
          ) : (
            'Analyze & Index Codebase'
          )}
        </button>
      </form>
    </div>
  );
}
