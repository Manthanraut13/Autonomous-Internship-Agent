import { useState, useEffect, useRef } from 'react';
import {
  Briefcase, Search, ExternalLink, Play, Settings, RefreshCw,
  Sparkles, Bot, Building2, X, MapPin, FileText, Mail,
  TrendingUp, Layers, Terminal, Trash2, Clock, CheckCircle,
  XCircle, Inbox, RotateCcw
} from 'lucide-react';
import './App.css';

/* ───────────────────────── Types ─────────────────────────────────── */

interface Job {
  id: number;
  job_id: string;
  title: string;
  company: string;
  description: string;
  link: string;
  apply_url: string;
  location: string;
  source: string;
  posted_at: string | null;
  scraped_at: string;
  updated_at: string;
  match_score: number | null;
  match_reasoning: string | null;
  status: string;
}

interface Stats {
  total_jobs: number;
  saved_count: number;
  applied_count: number;
  rejected_count: number;
  emailed_count: number;
  avg_match_score: number;
  sources_distribution: Record<string, number>;
  recent_activity: any[];
}

interface PipelineLog {
  step: string;
  message: string;
  timestamp: string;
  data?: any;
}

/* ───────────────────────── App ───────────────────────────────────── */

export default function App() {
  const [activeTab, setActiveTab] = useState<'jobs' | 'pipeline' | 'settings'>('jobs');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'saved' | 'applied' | 'rejected' | 'all'>('saved');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [agentSettings, setAgentSettings] = useState<any>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Pipeline state
  const [pipelineTarget, setPipelineTarget] = useState(25);
  const [pipelineThreshold, setPipelineThreshold] = useState(70);
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLog[]>([]);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  /* ── Data Fetching ────────────────────────────────────────────── */

  const fetchData = async () => {
    try {
      const [statsRes, jobsRes, settingsRes] = await Promise.all([
        fetch('/api/dashboard/stats'),
        fetch(`/api/dashboard/jobs?status=${statusFilter}&search=${searchQuery}&source=${sourceFilter}`),
        fetch('/api/dashboard/settings'),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (jobsRes.ok) {
        const data = await jobsRes.json();
        setJobs(data.jobs || []);
      }
      if (settingsRes.ok) setAgentSettings(await settingsRes.json());
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [statusFilter, searchQuery, sourceFilter]);
  useEffect(() => { const iv = setInterval(fetchData, 15000); return () => clearInterval(iv); }, [statusFilter, searchQuery, sourceFilter]);

  // Auto-scroll terminal
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [pipelineLogs]);

  /* ── Pipeline SSE ─────────────────────────────────────────────── */

  const runPipeline = () => {
    if (pipelineRunning) return;
    setPipelineRunning(true);
    setPipelineLogs([]);
    setActiveTab('pipeline');

    const es = new EventSource(`/api/pipeline/stream?target=${pipelineTarget}&threshold=${pipelineThreshold}`);

    es.addEventListener('pipeline', (event: MessageEvent) => {
      try {
        const log: PipelineLog = JSON.parse(event.data);
        setPipelineLogs(prev => [...prev, log]);

        if (log.step === 'complete' || log.step === 'error') {
          es.close();
          setPipelineRunning(false);
          fetchData(); // Refresh dashboard
          if (log.step === 'complete') {
            showToast(`✅ Pipeline finished — ${log.data?.matched || 0} jobs matched!`);
          }
        }
      } catch (e) {
        console.error('SSE parse error:', e);
      }
    });

    es.onerror = () => {
      es.close();
      setPipelineRunning(false);
      setPipelineLogs(prev => [...prev, {
        step: 'error',
        message: 'Connection closed or lost. Pipeline may still be running.',
        timestamp: new Date().toISOString(),
      }]);
    };
  };

  /* ── Job Actions ──────────────────────────────────────────────── */

  const handleJobAction = async (jobId: number, action: 'mark_applied' | 'mark_not_applied' | 'mark_saved' | 'delete', e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    try {
      const res = await fetch(`/api/dashboard/jobs/${jobId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      });
      if (res.ok) {
        if (selectedJob && selectedJob.id === jobId) {
          if (action === 'delete') {
            setSelectedJob(null);
          } else {
            const nextStatus = action === 'mark_applied' ? 'applied' : action === 'mark_not_applied' ? 'rejected' : 'saved';
            setSelectedJob({ ...selectedJob, status: nextStatus });
          }
        }
        fetchData();
        const actionLabels: Record<string, string> = {
          mark_applied: 'Marked as Applied! Moved to Applied section.',
          mark_not_applied: 'Marked as Not Applied. Moved to Not Applied section.',
          mark_saved: 'Moved back to Inbox.',
          delete: 'Job listing deleted.',
        };
        showToast(actionLabels[action] || 'Updated');
      }
    } catch (err) {
      console.error(err);
      showToast('Action failed');
    }
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  /* ── Helpers ──────────────────────────────────────────────────── */

  const getScoreClass = (score: number | null) => {
    if (score === null || score === undefined) return 'low';
    if (score >= 80) return 'high';
    if (score >= 60) return 'medium';
    return 'low';
  };

  const stepIcon = (step: string) => {
    switch (step) {
      case 'resume': return '📄';
      case 'queries': return '🧠';
      case 'scraping': return '🔍';
      case 'matching': return '⚡';
      case 'saving': return '💾';
      case 'csv': return '📊';
      case 'email': return '📧';
      case 'whatsapp': return '💬';
      case 'complete': return '✅';
      case 'error': return '❌';
      default: return '▸';
    }
  };

  const fmtTime = (iso: string) => {
    try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
    catch { return ''; }
  };

  /* ── Render ───────────────────────────────────────────────────── */

  return (
    <div className="app-container">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="header">
        <div className="header-left">
          <Bot size={28} />
          <h1>Internship <span>Agent</span></h1>
        </div>
        <button className="btn btn-primary" onClick={() => { runPipeline(); }} disabled={pipelineRunning}>
          <Play size={14} /> {pipelineRunning ? 'Running Pipeline...' : 'Run Pipeline'}
        </button>
      </div>

      {/* ── Main Tabs ───────────────────────────────────────────── */}
      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'jobs' ? 'active' : ''}`} onClick={() => setActiveTab('jobs')}>
          <Briefcase size={16} /> Openings & CRM
        </button>
        <button className={`tab-btn ${activeTab === 'pipeline' ? 'active' : ''}`} onClick={() => setActiveTab('pipeline')}>
          <Terminal size={16} /> Live Pipeline
        </button>
        <button className={`tab-btn ${activeTab === 'settings' ? 'active' : ''}`} onClick={() => setActiveTab('settings')}>
          <Settings size={16} /> Settings
        </button>
      </div>

      {/* ═══════════════════ JOBS & CRM TAB ═════════════════════════ */}
      {activeTab === 'jobs' && (
        <>
          {/* KPI Cards */}
          <div className="kpi-grid">
            <div className="kpi-card">
              <div className="kpi-label">Total Scraped</div>
              <div className="kpi-value accent">{stats?.total_jobs ?? '—'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Inbox (Unreviewed)</div>
              <div className="kpi-value yellow">{stats?.saved_count ?? '—'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Applied</div>
              <div className="kpi-value green">{stats?.applied_count ?? '—'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Emailed Reports</div>
              <div className="kpi-value blue">{stats?.emailed_count ?? '—'}</div>
            </div>
            <div className="kpi-card">
              <div className="kpi-label">Avg Match Score</div>
              <div className="kpi-value accent">{stats?.avg_match_score ?? '—'}</div>
            </div>
          </div>

          {/* Section Pills: Inbox / Applied / Not Applied / All */}
          <div className="status-pills">
            <button
              className={`status-pill ${statusFilter === 'saved' ? 'active' : ''}`}
              onClick={() => setStatusFilter('saved')}
            >
              <Inbox size={14} /> Inbox (New)
              <span className="pill-badge">{stats?.saved_count ?? 0}</span>
            </button>
            <button
              className={`status-pill ${statusFilter === 'applied' ? 'active' : ''}`}
              onClick={() => setStatusFilter('applied')}
            >
              <CheckCircle size={14} style={{ color: 'var(--green)' }} /> Applied
              <span className="pill-badge">{stats?.applied_count ?? 0}</span>
            </button>
            <button
              className={`status-pill ${statusFilter === 'rejected' ? 'active' : ''}`}
              onClick={() => setStatusFilter('rejected')}
            >
              <XCircle size={14} style={{ color: 'var(--red)' }} /> Not Applied
              <span className="pill-badge">{stats?.rejected_count ?? 0}</span>
            </button>
            <button
              className={`status-pill ${statusFilter === 'all' ? 'active' : ''}`}
              onClick={() => setStatusFilter('all')}
            >
              <Layers size={14} /> All Listings
              <span className="pill-badge">{stats?.total_jobs ?? 0}</span>
            </button>
          </div>

          {/* Controls Bar */}
          <div className="controls">
            <div className="search-box">
              <Search size={16} />
              <input
                placeholder="Search by title or company..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <select className="filter-select" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
              <option value="all">All Sources</option>
              <option value="remotive">Remotive</option>
              <option value="arbeitnow">Arbeitnow</option>
              <option value="himalayas">Himalayas</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="jsearch">JSearch</option>
            </select>
            <button className="btn btn-ghost" onClick={fetchData} title="Refresh data">
              <RefreshCw size={14} />
            </button>
          </div>

          {/* Scrollable Table */}
          <div className="table-wrap">
            <table className="jobs-table">
              <thead>
                <tr>
                  <th style={{ width: '28%' }}>Job Title</th>
                  <th style={{ width: '18%' }}>Company</th>
                  <th style={{ width: '15%' }}>Location</th>
                  <th style={{ width: '10%' }}>Source</th>
                  <th style={{ width: '9%' }}>Score</th>
                  <th style={{ width: '20%' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading openings...</td></tr>
                ) : jobs.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty-state">
                        <Inbox size={36} />
                        <p>
                          {statusFilter === 'saved'
                            ? 'Inbox is empty. Run the pipeline to discover new internships.'
                            : statusFilter === 'applied'
                            ? 'No applications tracked yet. Click "Applied" on any job to move it here.'
                            : statusFilter === 'rejected'
                            ? 'No rejected listings.'
                            : 'No jobs match the current search filters.'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : jobs.map((job) => (
                  <tr key={job.id} onClick={() => setSelectedJob(job)}>
                    <td style={{ fontWeight: 600 }}>{job.title}</td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                        <Building2 size={13} style={{ color: 'var(--text-muted)' }} /> {job.company}
                      </span>
                    </td>
                    <td>
                      <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-secondary)' }}>
                        <MapPin size={13} style={{ color: 'var(--text-muted)' }} /> {job.location || 'Remote'}
                      </span>
                    </td>
                    <td><span className="source-tag">{job.source}</span></td>
                    <td>
                      <span className={`score-badge ${getScoreClass(job.match_score)}`}>
                        <Sparkles size={11} /> {job.match_score ?? '—'}
                      </span>
                    </td>
                    <td>
                      <div className="row-actions" onClick={(e) => e.stopPropagation()}>
                        {/* 1. Apply Link */}
                        {(job.apply_url || job.link) && (
                          <a
                            href={job.apply_url || job.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="btn-action btn-apply"
                            title="Open direct job application link"
                          >
                            Apply <ExternalLink size={11} />
                          </a>
                        )}

                        {/* 2. Mark Applied Button */}
                        {job.status !== 'applied' && (
                          <button
                            className="btn-action btn-applied"
                            onClick={(e) => handleJobAction(job.id, 'mark_applied', e)}
                            title="Mark as Applied"
                          >
                            <CheckCircle size={12} /> Applied
                          </button>
                        )}

                        {/* 3. Mark Not Applied / Reject Button */}
                        {job.status !== 'rejected' && (
                          <button
                            className="btn-action btn-not-applied"
                            onClick={(e) => handleJobAction(job.id, 'mark_not_applied', e)}
                            title="Mark as Not Applied / Skip"
                          >
                            <XCircle size={12} /> Not Applied
                          </button>
                        )}

                        {/* Restore button if in applied or rejected tab */}
                        {job.status !== 'saved' && (
                          <button
                            className="btn-action btn-restore"
                            onClick={(e) => handleJobAction(job.id, 'mark_saved', e)}
                            title="Move back to Inbox"
                          >
                            <RotateCcw size={12} /> Inbox
                          </button>
                        )}

                        {/* 4. Delete Icon */}
                        <button
                          className="btn-delete-icon"
                          onClick={(e) => handleJobAction(job.id, 'delete', e)}
                          title="Delete Listing"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sources distribution chart */}
          {stats?.sources_distribution && Object.keys(stats.sources_distribution).length > 0 && (
            <div className="sources-chart">
              <h3><Layers size={14} /> Sources Distribution</h3>
              {(() => {
                const maxCount = Math.max(...Object.values(stats.sources_distribution));
                return Object.entries(stats.sources_distribution)
                  .sort(([, a], [, b]) => b - a)
                  .map(([source, count]) => (
                    <div className="source-bar-row" key={source}>
                      <span className="source-bar-label">{source}</span>
                      <div className="source-bar-track">
                        <div className="source-bar-fill" style={{ width: `${(count / maxCount) * 100}%` }} />
                      </div>
                      <span className="source-bar-count">{count}</span>
                    </div>
                  ));
              })()}
            </div>
          )}
        </>
      )}

      {/* ═══════════════════ LIVE PIPELINE TAB ═════════════════════ */}
      {activeTab === 'pipeline' && (
        <div className="pipeline-section">
          {/* Config Panel */}
          {/* Config Panel */}
          <div className="pipeline-config">
            <h3><Settings size={16} /> Pipeline Controls</h3>
            <div className="form-group">
              <label>Target Unique AI Matches</label>
              <input
                type="number"
                value={pipelineTarget}
                onChange={(e) => setPipelineTarget(parseInt(e.target.value) || 25)}
                min={1}
                max={50}
              />
            </div>
            <div className="form-group">
              <label>Match Score Threshold (0-100)</label>
              <input
                type="number"
                value={pipelineThreshold}
                onChange={(e) => setPipelineThreshold(parseInt(e.target.value) || 70)}
                min={0}
                max={100}
              />
            </div>
            <button className="execute-btn" onClick={runPipeline} disabled={pipelineRunning}>
              {pipelineRunning ? (
                <><RefreshCw size={16} className="spinner" /> Executing Pipeline...</>
              ) : (
                <><Play size={16} /> Execute Pipeline</>
              )}
            </button>
          </div>

          {/* Real Terminal with FIXED height and internal scrolling */}
          <div className="terminal">
            <div className="terminal-header">
              <span className="terminal-dot red" />
              <span className="terminal-dot yellow" />
              <span className="terminal-dot green" />
              <span className="terminal-title">pipeline-stream-output</span>
            </div>
            <div className="terminal-body" ref={terminalRef}>
              {pipelineLogs.length === 0 ? (
                <div className="terminal-idle">
                  <Terminal size={36} />
                  <span>Click "Execute Pipeline" to stream live logs here</span>
                </div>
              ) : (
                pipelineLogs.map((log, i) => (
                  <div className="terminal-line" key={i}>
                    <span className="timestamp">{fmtTime(log.timestamp)}</span>
                    <span className="step-icon">{stepIcon(log.step)}</span>
                    <span className={`msg ${log.step === 'error' ? 'red' : ['scraping', 'matching'].includes(log.step) && !log.message.includes('complete') ? 'dim' : ''}`}>
                      {log.message}
                    </span>
                  </div>
                ))
              )}
              {pipelineRunning && (
                <div className="terminal-line">
                  <span className="timestamp">&nbsp;</span>
                  <span className="step-icon"><RefreshCw size={12} className="spinner" /></span>
                  <span className="msg dim">Processing next step...</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ SETTINGS TAB ═════════════════════════ */}
      {activeTab === 'settings' && agentSettings && (
        <div className="settings-grid">
          <div className="setting-card">
            <h4><Clock size={14} /> Dual Cron Schedule</h4>
            <div className="setting-item">
              <span className="key">Morning Run</span>
              <span className="val" style={{ color: 'var(--green)' }}>09:00 AM (Daily)</span>
            </div>
            <div className="setting-item">
              <span className="key">Evening Run</span>
              <span className="val" style={{ color: 'var(--blue)' }}>09:00 PM (Daily)</span>
            </div>
            <div className="setting-item">
              <span className="key">Target Output</span>
              <span className="val">25 Unique Matches</span>
            </div>
            <div className="setting-item">
              <span className="key">Deduplication</span>
              <span className="val">Strict Cross-Run</span>
            </div>
          </div>
          <div className="setting-card">
            <h4><Bot size={14} /> AI Matcher</h4>
            <div className="setting-item"><span className="key">Groq Model</span><span className="val">{agentSettings.groq_model}</span></div>
            <div className="setting-item"><span className="key">Match Threshold</span><span className="val">{agentSettings.match_score_threshold}%</span></div>
          </div>
          <div className="setting-card">
            <h4><Mail size={14} /> Notifications</h4>
            <div className="setting-item"><span className="key">Recipient Email</span><span className="val">{agentSettings.recipient_email}</span></div>
            <div className="setting-item"><span className="key">WhatsApp Number</span><span className="val">{agentSettings.user_whatsapp_number || 'Not set'}</span></div>
          </div>
          <div className="setting-card">
            <h4><FileText size={14} /> Candidate Profile</h4>
            <div className="setting-item"><span className="key">Name</span><span className="val">{agentSettings.candidate_name}</span></div>
            <div className="setting-item"><span className="key">Email</span><span className="val">{agentSettings.candidate_email}</span></div>
          </div>
          <div className="setting-card">
            <h4><Layers size={14} /> Configured Sources</h4>
            <div className="setting-item"><span className="key">Platforms</span><span className="val">{(agentSettings.job_sources || []).join(', ')}</span></div>
          </div>
        </div>
      )}

      {/* ═══════════════════ JOB DETAIL MODAL ════════════════════════ */}
      {selectedJob && (
        <div className="modal-overlay" onClick={() => setSelectedJob(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{selectedJob.title}</h2>
              <button className="modal-close" onClick={() => setSelectedJob(null)}><X size={16} /></button>
            </div>
            <div className="modal-body">
              <div className="detail-row">
                <Building2 size={16} />
                <div><div className="label">Company</div><div className="value">{selectedJob.company}</div></div>
              </div>
              <div className="detail-row">
                <MapPin size={16} />
                <div><div className="label">Location</div><div className="value">{selectedJob.location || 'Remote / Unspecified'}</div></div>
              </div>
              <div className="detail-row">
                <TrendingUp size={16} />
                <div>
                  <div className="label">Match Score</div>
                  <div className="value">
                    <span className={`score-badge ${getScoreClass(selectedJob.match_score)}`}>
                      <Sparkles size={12} /> {selectedJob.match_score ?? '—'}/100
                    </span>
                  </div>
                </div>
              </div>
              {selectedJob.match_reasoning && (
                <div className="detail-row">
                  <FileText size={16} />
                  <div>
                    <div className="label">AI Match Reasoning</div>
                    <div className="value" style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)' }}>
                      {selectedJob.match_reasoning}
                    </div>
                  </div>
                </div>
              )}
              {selectedJob.posted_at && (
                <div className="detail-row">
                  <Clock size={16} />
                  <div><div className="label">Date Posted</div><div className="value">{new Date(selectedJob.posted_at).toLocaleDateString()}</div></div>
                </div>
              )}
              {selectedJob.description && (
                <div className="detail-row">
                  <FileText size={16} />
                  <div>
                    <div className="label">Job Description</div>
                    <div className="value" style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-secondary)', maxHeight: 180, overflow: 'auto' }}>
                      {selectedJob.description.slice(0, 1000)}{selectedJob.description.length > 1000 ? '...' : ''}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="modal-footer">
              {(selectedJob.apply_url || selectedJob.link) && (
                <a href={selectedJob.apply_url || selectedJob.link} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
                  <ExternalLink size={14} /> Open Apply Link
                </a>
              )}
              {selectedJob.status !== 'applied' && (
                <button className="btn btn-success" onClick={() => handleJobAction(selectedJob.id, 'mark_applied')}>
                  <CheckCircle size={14} /> Mark as Applied
                </button>
              )}
              {selectedJob.status !== 'rejected' && (
                <button className="btn btn-danger" onClick={() => handleJobAction(selectedJob.id, 'mark_not_applied')}>
                  <XCircle size={14} /> Mark as Not Applied
                </button>
              )}
              <button className="btn btn-danger" onClick={() => handleJobAction(selectedJob.id, 'delete')}>
                <Trash2 size={14} /> Delete Listing
              </button>
              <button className="btn btn-ghost" onClick={() => setSelectedJob(null)}>Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toastMessage && <div className="toast">{toastMessage}</div>}
    </div>
  );
}
