import React, { useState, useEffect, useRef } from 'react';
import './App.css';

/* ─────────────────────────────────────────────────────────────────────────── */
/* Types & Interfaces                                                         */
/* ─────────────────────────────────────────────────────────────────────────── */

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

/* ─────────────────────────────────────────────────────────────────────────── */
/* Helper Functions                                                           */
/* ─────────────────────────────────────────────────────────────────────────── */

function extractSkills(description: string, title: string): string[] {
  const common = [
    'Python', 'PyTorch', 'TensorFlow', 'LangChain', 'LLMs', 'OpenAI',
    'Groq', 'FastAPI', 'React', 'TypeScript', 'Next.js', 'NLP',
    'Computer Vision', 'RAG', 'Agentic AI', 'HuggingFace', 'Docker',
    'SQL', 'PostgreSQL', 'APIs', 'AWS', 'GCP', 'Llama'
  ];
  const text = `${title} ${description}`.toLowerCase();
  const matched = common.filter(skill => text.includes(skill.toLowerCase()));
  return matched.slice(0, 4);
}

function getScoreColor(score: number): { stroke: string; text: string; bg: string } {
  if (score >= 80) return { stroke: '#006b5c', text: '#006b5c', bg: '#eefcf8' }; // Tertiary/Seafoam
  if (score >= 70) return { stroke: '#5b9bd5', text: '#136299', bg: '#eef4ff' }; // Primary/Steel Blue
  if (score >= 50) return { stroke: '#e8a94a', text: '#b45309', bg: '#fef3c7' }; // Score Mid/Amber
  return { stroke: '#d66b6b', text: '#ba1a1a', bg: '#fee2e2' };                  // Score Low/Error
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Main Application Component                                                 */
/* ─────────────────────────────────────────────────────────────────────────── */

export default function App() {
  // Authentication State
  const [authToken, setAuthToken] = useState<string | null>(localStorage.getItem('internship_agent_token'));
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [loginUsername, setLoginUsername] = useState('admin');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState(false);
  const [currentUser, setCurrentUser] = useState<string>('admin');

  // Navigation & Tabs
  const [activeTab, setActiveTab] = useState<'dashboard' | 'jobs' | 'pipeline' | 'resume' | 'settings'>('dashboard');

  // Data & Filters
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'saved' | 'applied' | 'rejected'>('all');
  const [sourceFilter, setSourceFilter] = useState('all');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(70);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [agentSettings, setAgentSettings] = useState<any>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Resume Upload Modal State
  const [isResumeModalOpen, setIsResumeModalOpen] = useState(false);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [isUploadingResume, setIsUploadingResume] = useState(false);

  // Pipeline Execution State
  const [pipelineTarget, setPipelineTarget] = useState(25);
  const [pipelineThreshold, setPipelineThreshold] = useState(70);
  const [pipelineLogs, setPipelineLogs] = useState<PipelineLog[]>([
    { step: 'init', message: 'Agent core initialized. Ready to execute sourcing pipeline.', timestamp: new Date().toLocaleTimeString() }
  ]);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const terminalRef = useRef<HTMLDivElement>(null);

  // Show Toast
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  /* ── Auth Verification ─────────────────────────────────────────────────── */

  useEffect(() => {
    const verifyToken = async () => {
      const savedToken = localStorage.getItem('internship_agent_token');
      if (!savedToken) {
        setIsAuthenticated(false);
        setLoading(false);
        return;
      }
      try {
        const res = await fetch('/api/auth/me', {
          headers: { 'Authorization': `Bearer ${savedToken}` }
        });
        if (res.ok) {
          const data = await res.json();
          setAuthToken(savedToken);
          setIsAuthenticated(true);
          setCurrentUser(data.username || 'admin');
        } else {
          localStorage.removeItem('internship_agent_token');
          setAuthToken(null);
          setIsAuthenticated(false);
        }
      } catch (err) {
        console.error('Auth verification error:', err);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };
    verifyToken();
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setLoggingIn(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      const data = await res.json();
      if (res.ok && data.token) {
        localStorage.setItem('internship_agent_token', data.token);
        setAuthToken(data.token);
        setIsAuthenticated(true);
        setCurrentUser(data.username || loginUsername);
        showToast('Authentication successful!');
      } else {
        setLoginError(data.detail || 'Invalid username or password.');
      }
    } catch (err) {
      setLoginError('Could not connect to backend server.');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('internship_agent_token');
    setAuthToken(null);
    setIsAuthenticated(false);
    showToast('Logged out successfully.');
  };

  /* ── Data Fetching ─────────────────────────────────────────────────────── */

  const fetchData = async () => {
    if (!authToken || !isAuthenticated) return;
    setLoading(true);
    try {
      const headers = { 'Authorization': `Bearer ${authToken}` };

      // Fetch Stats
      const statsRes = await fetch('/api/dashboard/stats', { headers });
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      // Fetch Jobs
      let jobsUrl = `/api/dashboard/jobs?sort_by=match_score&order=desc`;
      if (statusFilter !== 'all') jobsUrl += `&status=${statusFilter}`;
      if (sourceFilter !== 'all') jobsUrl += `&source=${sourceFilter}`;
      if (searchQuery) jobsUrl += `&search=${encodeURIComponent(searchQuery)}`;

      const jobsRes = await fetch(jobsUrl, { headers });
      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData.jobs || []);
      }

      // Fetch Settings
      const settingsRes = await fetch('/api/dashboard/settings', { headers });
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setAgentSettings(settingsData);
        if (settingsData.match_score_threshold) {
          setPipelineThreshold(settingsData.match_score_threshold);
        }
      }
    } catch (err) {
      console.error('Error fetching data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchData();
    }
  }, [isAuthenticated, statusFilter, sourceFilter, searchQuery]);

  /* ── Job Actions ───────────────────────────────────────────────────────── */

  const handleJobAction = async (jobId: number, action: 'mark_applied' | 'reject' | 'mark_saved' | 'delete') => {
    if (!authToken) return;
    try {
      const res = await fetch(`/api/dashboard/jobs/${jobId}/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({ action })
      });
      if (res.ok) {
        const data = await res.json();
        showToast(data.message || 'Status updated');
        // Optimistic state update
        setJobs(prev => prev.map(j => {
          if (j.id === jobId) {
            if (action === 'mark_applied') return { ...j, status: 'applied' };
            if (action === 'reject') return { ...j, status: 'rejected' };
            if (action === 'mark_saved') return { ...j, status: 'saved' };
          }
          return j;
        }).filter(j => action === 'delete' ? j.id !== jobId : true));
        fetchData();
      }
    } catch (err) {
      console.error('Job action error:', err);
      showToast('Action failed');
    }
  };

  /* ── Live SSE Pipeline Execution ───────────────────────────────────────── */

  const runPipeline = () => {
    if (pipelineRunning || !authToken) return;

    setPipelineRunning(true);
    setPipelineLogs([{
      step: 'init',
      message: `Starting priority search (Target: ${pipelineTarget} qualified AI internship openings, Min Score: ${pipelineThreshold})...`,
      timestamp: new Date().toLocaleTimeString()
    }]);

    const sseUrl = `/api/pipeline/stream?target=${pipelineTarget}&threshold=${pipelineThreshold}&token=${encodeURIComponent(authToken)}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.addEventListener('pipeline', (e: MessageEvent) => {
      try {
        const payload: PipelineLog = JSON.parse(e.data);
        setPipelineLogs(prev => [...prev, payload]);
        if (payload.data && payload.data.job) {
          setJobs(prev => [payload.data.job, ...prev]);
        }
      } catch (err) {
        console.error('Failed to parse SSE payload:', err);
      }
    });

    eventSource.onerror = () => {
      eventSource.close();
      setPipelineRunning(false);
      setPipelineLogs(prev => [...prev, {
        step: 'complete',
        message: 'Pipeline execution finished.',
        timestamp: new Date().toLocaleTimeString()
      }]);
      fetchData();
    };
  };

  // Auto-scroll terminal to bottom
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [pipelineLogs]);

  /* ── Resume Upload Handler ─────────────────────────────────────────────── */

  const handleResumeUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resumeFile || !authToken) return;

    setIsUploadingResume(true);
    const formData = new FormData();
    formData.append('file', resumeFile);

    try {
      const res = await fetch('/upload-resume', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${authToken}` },
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || 'Resume uploaded successfully!');
        setIsResumeModalOpen(false);
        setResumeFile(null);
      } else {
        showToast(data.detail || 'Failed to upload resume.');
      }
    } catch (err) {
      showToast('Error uploading resume file.');
    } finally {
      setIsUploadingResume(false);
    }
  };

  /* ── Filtered Jobs for Display ─────────────────────────────────────────── */

  const displayedJobs = jobs.filter(j => {
    if (minScoreFilter > 0 && (j.match_score || 0) < minScoreFilter) return false;
    return true;
  });

  /* ───────────────────────────────────────────────────────────────────────── */
  /* Unauthenticated Login Screen                                              */
  /* ───────────────────────────────────────────────────────────────────────── */

  if (!isAuthenticated && !loading) {
    return (
      <div className="min-h-screen bg-[#eef2f7] flex items-center justify-center p-4 font-body-main">
        <div className="bg-[#ffffff] rounded-2xl p-8 max-w-md w-full border border-[#d4dde8] shadow-[0_16px_40px_rgba(15,28,43,0.08)]">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-xl bg-[#5b9bd5]/20 flex items-center justify-center">
              <span className="material-symbols-outlined text-[#136299] text-[24px]">account_tree</span>
            </div>
            <div>
              <h1 className="text-[20px] font-bold text-[#0f1c2b] tracking-tight">Agent Core</h1>
              <p className="text-[12px] text-[#7a95b0]">Autonomous Internship Agent</p>
            </div>
          </div>

          <div className="mb-6 bg-[#eef4ff] p-3 rounded-lg border border-[#cfe5ff]">
            <p className="text-[12px] text-[#41474f] leading-relaxed">
              Sign in with your admin credentials to monitor and control your AI Sourcing Agent.
            </p>
          </div>

          {loginError && (
            <div className="mb-4 p-3 bg-[#ffdad6] text-[#ba1a1a] text-[12px] rounded-lg font-semibold flex items-center gap-2">
              <span className="material-symbols-outlined text-[16px]">error</span>
              {loginError}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-[11px] font-semibold uppercase text-[#4a6080] mb-1">Username</label>
              <input
                type="text"
                value={loginUsername}
                onChange={e => setLoginUsername(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#f8f9ff] border border-[#d4dde8] rounded-lg text-[13px] text-[#0f1c2b] focus:outline-none focus:border-[#136299] focus:ring-2 focus:ring-[#136299]/15 transition-all"
                placeholder="admin"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold uppercase text-[#4a6080] mb-1">Password</label>
              <input
                type="password"
                value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)}
                required
                className="w-full px-3 py-2 bg-[#f8f9ff] border border-[#d4dde8] rounded-lg text-[13px] text-[#0f1c2b] focus:outline-none focus:border-[#136299] focus:ring-2 focus:ring-[#136299]/15 transition-all"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loggingIn}
              className="w-full bg-[#136299] hover:bg-[#004a77] text-white py-2.5 rounded-lg font-semibold text-[13px] transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2 mt-2 cursor-pointer"
            >
              {loggingIn ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-[16px]">sync</span>
                  Authenticating...
                </>
              ) : (
                <>
                  <span className="material-symbols-outlined text-[16px]">lock_open</span>
                  Sign In to Dashboard
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    );
  }

  /* ───────────────────────────────────────────────────────────────────────── */
  /* Main Dashboard (Glacial Precision Design System)                          */
  /* ───────────────────────────────────────────────────────────────────────── */

  return (
    <div className="app-container">
      {/* ── Fixed Left Sidebar ────────────────────────────────────────────── */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="material-symbols-outlined text-[#136299] text-[24px]">account_tree</span>
          <span className="font-bold text-[13px] text-[#003151] tracking-wider uppercase font-mono">Agent Core</span>
        </div>

        <nav className="sidebar-nav">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`sidebar-link ${activeTab === 'dashboard' ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined mr-3 text-[20px]">dashboard</span>
            <span>Dashboard</span>
          </button>

          <button
            onClick={() => setActiveTab('jobs')}
            className={`sidebar-link ${activeTab === 'jobs' ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined mr-3 text-[20px]">work</span>
            <span>Jobs</span>
          </button>

          <button
            onClick={() => setActiveTab('pipeline')}
            className={`sidebar-link ${activeTab === 'pipeline' ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined mr-3 text-[20px]">reorder</span>
            <span>Pipeline</span>
          </button>

          <button
            onClick={() => setActiveTab('resume')}
            className={`sidebar-link ${activeTab === 'resume' ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined mr-3 text-[20px]">description</span>
            <span>Resume</span>
          </button>

          <button
            onClick={() => setActiveTab('settings')}
            className={`sidebar-link ${activeTab === 'settings' ? 'active' : ''}`}
          >
            <span className="material-symbols-outlined mr-3 text-[20px]">settings</span>
            <span>Settings</span>
          </button>
        </nav>

        {/* Agent Status Box */}
        <div className="sidebar-status-card">
          <div className="text-[11px] font-semibold text-[#7a95b0] uppercase tracking-wider mb-2">Agent Status</div>
          <div className="inline-flex items-center px-3 py-1 bg-[#39a794]/15 text-[#006b5c] rounded-full border border-[#39a794]/30">
            <div className="pulse-dot mr-2"></div>
            <span className="text-[11px] font-bold uppercase tracking-wider">Active</span>
          </div>
        </div>
      </aside>

      {/* ── Main Layout Wrapper ───────────────────────────────────────────── */}
      <div className="main-wrapper">
        {/* ── Fixed Top Header ────────────────────────────────────────────── */}
        <header className="top-header">
          <div className="flex items-center gap-3">
            <h1 className="text-[20px] font-bold text-[#0f1c2b] tracking-tight">Internship Agent</h1>
            <span className="text-[12px] text-[#7a95b0] font-medium hidden sm:inline">• Strictly Remote, Online & Virtual AI Sourcing</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Live Pipeline Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[#e4efff] rounded-full border border-[#c1c7d1]/30">
              <div className="pulse-dot"></div>
              <span className="text-[12px] font-semibold text-[#41474f]">Remote Sourcing Active</span>
            </div>


            {/* Quick Resume Upload Button */}
            <button
              onClick={() => setIsResumeModalOpen(true)}
              className="p-2 hover:bg-[#e4efff] text-[#41474f] hover:text-[#136299] rounded-full transition-colors"
              title="Upload Master Resume"
            >
              <span className="material-symbols-outlined text-[20px]">upload_file</span>
            </button>

            {/* User Profile & Logout */}
            <div className="flex items-center gap-2 pl-2 border-l border-[#d4dde8]">
              <div className="w-8 h-8 rounded-full bg-[#136299] text-white flex items-center justify-center font-bold text-[12px]">
                {currentUser[0]?.toUpperCase() || 'A'}
              </div>
              <button
                onClick={handleLogout}
                className="p-1.5 hover:bg-[#ffdad6] text-[#717880] hover:text-[#ba1a1a] rounded-lg transition-colors cursor-pointer"
                title="Log Out"
              >
                <span className="material-symbols-outlined text-[18px]">logout</span>
              </button>
            </div>
          </div>
        </header>

        {/* ── Dynamic Content Container ───────────────────────────────────── */}
        <main className="content-area">
          {/* Toast Alert */}
          {toastMessage && (
            <div className="fixed bottom-6 right-6 z-50 bg-[#0f1c2b] text-white px-4 py-3 rounded-xl shadow-xl flex items-center gap-2 text-[13px] border border-[#5b9bd5]/40 animate-bounce">
              <span className="material-symbols-outlined text-[#39a794] text-[18px]">info</span>
              {toastMessage}
            </div>
          )}

          {/* ───────────────────────────────────────────────────────────────── */}
          {/* TAB 1: DASHBOARD & JOBS VIEW                                     */}
          {/* ───────────────────────────────────────────────────────────────── */}
          {(activeTab === 'dashboard' || activeTab === 'jobs') && (
            <div className="space-y-6">
              {/* KPI Metrics Row */}
              <div className="kpi-grid">
                {/* Metric 1: Scraped */}
                <div className="kpi-card" style={{ borderLeftColor: '#5b9bd5' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[#4a6080] font-bold uppercase tracking-wider text-[11px]">Scraped</span>
                    <span className="material-symbols-outlined text-[#5b9bd5] text-[20px]">search</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <span className="text-[26px] font-bold text-[#0f1c2b] leading-none">
                      {stats?.total_jobs ?? jobs.length}
                    </span>
                    <span className="text-[11px] text-[#7a95b0] mb-0.5">+12% today</span>
                  </div>
                </div>

                {/* Metric 2: Qualified */}
                <div className="kpi-card" style={{ borderLeftColor: '#39a794' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[#4a6080] font-bold uppercase tracking-wider text-[11px]">Qualified</span>
                    <span className="material-symbols-outlined text-[#39a794] text-[20px]">check_circle</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <span className="text-[26px] font-bold text-[#0f1c2b] leading-none">
                      {jobs.filter(j => (j.match_score || 0) >= 70).length}
                    </span>
                    <span className="text-[11px] text-[#7a95b0] mb-0.5">Score ≥ 70</span>
                  </div>
                </div>

                {/* Metric 3: Applied */}
                <div className="kpi-card" style={{ borderLeftColor: '#984623' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[#4a6080] font-bold uppercase tracking-wider text-[11px]">Applied</span>
                    <span className="material-symbols-outlined text-[#984623] text-[20px]">send</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <span className="text-[26px] font-bold text-[#0f1c2b] leading-none">
                      {stats?.applied_count ?? jobs.filter(j => j.status === 'applied').length}
                    </span>
                    <span className="text-[11px] text-[#7a95b0] mb-0.5">Submitted</span>
                  </div>
                </div>

                {/* Metric 4: Pipeline Runs */}
                <div className="kpi-card" style={{ borderLeftColor: '#e8a94a' }}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[#4a6080] font-bold uppercase tracking-wider text-[11px]">Pipeline Runs</span>
                    <span className="material-symbols-outlined text-[#e8a94a] text-[20px]">autorenew</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <span className="text-[26px] font-bold text-[#0f1c2b] leading-none">
                      {stats?.emailed_count ? stats.emailed_count + 1 : 2}
                    </span>
                    <span className="text-[11px] text-[#7a95b0] mb-0.5">Dual Daily Cron</span>
                  </div>
                </div>
              </div>

              {/* Filter Toolbar */}
              <div className="toolbar-card">
                <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
                  {/* Search Input */}
                  <div className="search-input-group flex-1 lg:flex-none">
                    <span className="material-symbols-outlined search-icon">search</span>
                    <input
                      type="text"
                      placeholder="Search roles, companies..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                    />
                  </div>

                  {/* Platform Dropdown */}
                  <select
                    className="select-filter"
                    value={sourceFilter}
                    onChange={e => setSourceFilter(e.target.value)}
                  >
                    <option value="all">All Platforms</option>
                    <option value="linkedin">LinkedIn Startups</option>
                    <option value="remotive">Remotive Startups</option>
                    <option value="himalayas">Himalayas Startups</option>
                  </select>

                  {/* Score Slider */}
                  <div className="flex items-center gap-2 bg-[#f8f9ff] px-3 py-1.5 rounded-lg border border-[#d4dde8]">
                    <span className="text-[11px] font-bold text-[#4a6080] uppercase">Score &gt;</span>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={minScoreFilter}
                      onChange={e => setMinScoreFilter(Number(e.target.value))}
                      className="w-20 accent-[#136299] cursor-pointer"
                    />
                    <span className="text-[11px] font-bold text-[#0f1c2b] w-6">{minScoreFilter}</span>
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto justify-between lg:justify-end">
                  {/* Status Pills */}
                  <div className="status-pill-group">
                    {(['all', 'saved', 'applied', 'rejected'] as const).map(st => (
                      <button
                        key={st}
                        onClick={() => setStatusFilter(st)}
                        className={`status-pill-btn ${statusFilter === st ? 'active' : ''}`}
                      >
                        {st.toUpperCase()}
                      </button>
                    ))}
                  </div>

                  {/* Run Pipeline Action Button */}
                  <button
                    onClick={runPipeline}
                    disabled={pipelineRunning}
                    className="btn-primary"
                  >
                    {pipelineRunning ? (
                      <>
                        <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                        Running...
                      </>
                    ) : (
                      <>
                        <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                        Run Pipeline
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Two-Column Grid: Left (Console) | Right (Job Cards) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* ── Column 1: Live Agent Console (4 cols on lg) ─────────── */}
                <div className="lg:col-span-4 flex flex-col">
                  <div className="terminal-card">
                    <div className="terminal-header">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-[#39a794] text-[16px]">terminal</span>
                        <span className="text-[11px] font-bold text-[#39a794] uppercase tracking-wider font-mono">Agent Console</span>
                      </div>
                      <div className="flex gap-1.5">
                        <div className="w-2.5 h-2.5 rounded-full bg-[#ba1a1a]/60"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#e8a94a]/60"></div>
                        <div className="w-2.5 h-2.5 rounded-full bg-[#006b5c]/60"></div>
                      </div>
                    </div>

                    <div className="terminal-body" ref={terminalRef}>
                      {pipelineLogs.map((log, index) => {
                        let tagColor = 'text-[#98cbff]';
                        if (log.message.includes('FOUND') || log.message.includes('Scoring') || log.message.includes('Scored')) tagColor = 'text-[#70d8c3]';
                        if (log.message.includes('SUCCESS') || log.message.includes('Finished') || log.message.includes('Saved')) tagColor = 'text-[#5b9bd5]';
                        if (log.message.includes('Error') || log.message.includes('FAIL') || log.message.includes('404')) tagColor = 'text-[#d66b6b]';

                        return (
                          <div key={index} className="log-line">
                            <span className="text-[#7a95b0]">[{log.timestamp}]</span>{' '}
                            <span className={`font-semibold ${tagColor}`}>{log.step.toUpperCase()}</span>{' '}
                            <span>{log.message}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>

                {/* ── Column 2: Job Cards Grid (8 cols on lg) ─────────────── */}
                <div className="lg:col-span-8">
                  {loading && jobs.length === 0 ? (
                    <div className="bg-[#ffffff] rounded-xl p-12 text-center border border-[#d4dde8]">
                      <span className="material-symbols-outlined animate-spin text-[#136299] text-[36px] mb-3">sync</span>
                      <p className="text-[14px] font-semibold text-[#0f1c2b]">Loading fresh internship listings...</p>
                    </div>
                  ) : displayedJobs.length === 0 ? (
                    <div className="bg-[#ffffff] rounded-xl p-12 text-center border border-[#d4dde8]">
                      <span className="material-symbols-outlined text-[#7a95b0] text-[48px] mb-2">inbox</span>
                      <h3 className="text-[16px] font-bold text-[#0f1c2b] mb-1">No matching openings found</h3>
                      <p className="text-[13px] text-[#7a95b0] mb-4">Try adjusting your search query, score slider, or click "Run Pipeline" to discover fresh AI roles.</p>
                      <button onClick={runPipeline} className="btn-primary">
                        <span className="material-symbols-outlined text-[16px]">play_arrow</span>
                        Trigger Sourcing Pipeline
                      </button>
                    </div>
                  ) : (
                    <div className="job-cards-grid">
                      {displayedJobs.map(job => {
                        const score = job.match_score ?? 0;
                        const scoreStyle = getScoreColor(score);
                        const skills = extractSkills(job.description, job.title);

                        return (
                          <div key={job.id} className="job-card group">
                            {/* Card Header: Title & Circular Score Ring */}
                            <div className="flex justify-between items-start gap-2 mb-3">
                              <div className="flex-1">
                                <h3 className="job-title">{job.title}</h3>
                                <p className="job-meta">
                                  <span className="font-semibold text-[#0f1c2b]">{job.company}</span> • {job.location || 'Remote'}
                                </p>
                              </div>

                              {/* Circular SVG Score Ring */}
                              <div className="relative w-[48px] h-[48px] flex items-center justify-center shrink-0">
                                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                                  <path
                                    className="text-[#dce9fe]"
                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                  />
                                  <path
                                    d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                                    fill="none"
                                    stroke={scoreStyle.stroke}
                                    strokeDasharray={`${score}, 100`}
                                    strokeWidth="3"
                                    className="transition-all duration-1000 ease-out"
                                  />
                                </svg>
                                <span className="absolute text-[13px] font-bold" style={{ color: scoreStyle.text }}>
                                  {score}
                                </span>
                              </div>
                            </div>

                            {/* Tags & Skills */}
                            <div className="flex flex-wrap gap-1.5 mb-4">
                              <span className="tag-badge bg-[#eefcf8] text-[#006b5c] border-[#8df5df]">
                                <span className="material-symbols-outlined text-[13px]">wifi</span>
                                REMOTE / VIRTUAL
                              </span>
                              <span className="tag-badge">
                                <span className="material-symbols-outlined text-[13px]">hub</span>
                                {job.source.toUpperCase()}
                              </span>
                              {skills.map(s => (
                                <span key={s} className="tag-badge bg-[#eef4ff] text-[#136299] border-[#cfe5ff]">
                                  {s}
                                </span>
                              ))}
                              {job.status === 'applied' && (
                                <span className="tag-badge bg-[#eefcf8] text-[#006b5c] border-[#8df5df]">
                                  APPLIED
                                </span>
                              )}
                            </div>

                            {/* AI Match Reasoning Snippet */}
                            {job.match_reasoning && (
                              <p className="text-[12px] text-[#41474f] bg-[#f8f9ff] p-2.5 rounded-lg border border-[#d4dde8] line-clamp-2 mb-4 leading-relaxed">
                                {job.match_reasoning}
                              </p>
                            )}

                            {/* Card Footer Actions */}
                            <div className="mt-auto flex items-center gap-2 pt-2 border-t border-[#d4dde8]">
                              <a
                                href={job.apply_url || job.link}
                                target="_blank"
                                rel="noreferrer"
                                className="flex-1 bg-[#136299] hover:bg-[#004a77] text-white py-2 px-3 rounded-lg font-semibold text-[12px] transition-colors text-center inline-flex items-center justify-center gap-1.5"
                              >
                                <span>Apply Now</span>
                                <span className="material-symbols-outlined text-[14px]">open_in_new</span>
                              </a>

                              <button
                                onClick={() => handleJobAction(job.id, 'mark_applied')}
                                className={`p-2 rounded-lg transition-colors cursor-pointer ${
                                  job.status === 'applied'
                                    ? 'bg-[#39a794] text-white'
                                    : 'bg-[#f8f9ff] text-[#4a6080] hover:bg-[#39a794]/20 hover:text-[#006b5c] border border-[#d4dde8]'
                                }`}
                                title="Mark as Applied"
                              >
                                <span className="material-symbols-outlined text-[18px]">done</span>
                              </button>

                              <button
                                onClick={() => handleJobAction(job.id, 'reject')}
                                className="p-2 bg-[#f8f9ff] text-[#717880] hover:text-[#ba1a1a] hover:bg-[#ffdad6] rounded-lg border border-[#d4dde8] transition-colors cursor-pointer"
                                title="Reject"
                              >
                                <span className="material-symbols-outlined text-[18px]">close</span>
                              </button>

                              <button
                                onClick={() => setSelectedJob(job)}
                                className="p-2 bg-[#f8f9ff] text-[#717880] hover:text-[#0f1c2b] hover:bg-[#e4efff] rounded-lg border border-[#d4dde8] transition-colors cursor-pointer"
                                title="View Details"
                              >
                                <span className="material-symbols-outlined text-[18px]">visibility</span>
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ───────────────────────────────────────────────────────────────── */}
          {/* TAB 2: PIPELINE EXECUTION TAB                                    */}
          {/* ───────────────────────────────────────────────────────────────── */}
          {activeTab === 'pipeline' && (
            <div className="space-y-6">
              <div className="bg-[#ffffff] rounded-xl p-6 border border-[#d4dde8] shadow-sm">
                <h2 className="text-[18px] font-bold text-[#0f1c2b] mb-4 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#136299]">tune</span>
                  Pipeline Orchestration Settings
                </h2>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                  <div>
                    <label className="block text-[11px] font-bold uppercase text-[#4a6080] mb-2">Target Qualified Matches</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="5"
                        max="50"
                        value={pipelineTarget}
                        onChange={e => setPipelineTarget(Number(e.target.value))}
                        className="flex-1 accent-[#136299]"
                      />
                      <span className="text-[14px] font-bold text-[#0f1c2b] bg-[#f8f9ff] px-3 py-1 rounded-lg border border-[#d4dde8]">
                        {pipelineTarget}
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold uppercase text-[#4a6080] mb-2">Minimum Match Score</label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="50"
                        max="95"
                        value={pipelineThreshold}
                        onChange={e => setPipelineThreshold(Number(e.target.value))}
                        className="flex-1 accent-[#136299]"
                      />
                      <span className="text-[14px] font-bold text-[#0f1c2b] bg-[#f8f9ff] px-3 py-1 rounded-lg border border-[#d4dde8]">
                        {pipelineThreshold}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-end">
                    <button
                      onClick={runPipeline}
                      disabled={pipelineRunning}
                      className="w-full btn-primary h-[42px]"
                    >
                      {pipelineRunning ? (
                        <>
                          <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                          Executing Pipeline...
                        </>
                      ) : (
                        <>
                          <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                          Run Autonomous Pipeline Now
                        </>
                      )}
                    </button>
                  </div>
                </div>

                {/* Priority Hierarchy Visualizer */}
                <div className="bg-[#f8f9ff] p-4 rounded-xl border border-[#d4dde8]">
                  <h4 className="text-[12px] font-bold uppercase text-[#0f1c2b] mb-2">Active Scraper Priority Cascade</h4>
                  <div className="flex flex-wrap items-center gap-2 text-[12px]">
                    <span className="px-3 py-1 bg-[#136299] text-white font-semibold rounded-lg">1. LinkedIn Startups</span>
                    <span className="text-[#7a95b0]">→</span>
                    <span className="px-3 py-1 bg-[#5b9bd5] text-white font-semibold rounded-lg">2. Remotive Startups</span>
                    <span className="text-[#7a95b0]">→</span>
                    <span className="px-3 py-1 bg-[#39a794] text-white font-semibold rounded-lg">3. Himalayas Startups</span>
                    <span className="text-[#7a95b0]">→</span>
                    <span className="px-3 py-1 bg-[#eef4ff] text-[#003151] font-semibold rounded-lg border border-[#cfe5ff]">
                      🛑 Immediate Early-Stop at {pipelineTarget} matches
                    </span>
                  </div>
                </div>
              </div>

              {/* Full-width Terminal Console */}
              <div className="terminal-card" style={{ height: '480px' }}>
                <div className="terminal-header">
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[#39a794] text-[16px]">terminal</span>
                    <span className="text-[11px] font-bold text-[#39a794] uppercase tracking-wider font-mono">Real-Time Autonomous Stream</span>
                  </div>
                  <button
                    onClick={() => setPipelineLogs([])}
                    className="text-[11px] text-[#7a95b0] hover:text-white transition-colors"
                  >
                    Clear Output
                  </button>
                </div>
                <div className="terminal-body" ref={terminalRef}>
                  {pipelineLogs.map((log, i) => (
                    <div key={i} className="log-line">
                      <span className="text-[#7a95b0]">[{log.timestamp}]</span>{' '}
                      <span className="text-[#98cbff] font-semibold">{log.step.toUpperCase()}</span>{' '}
                      <span>{log.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ───────────────────────────────────────────────────────────────── */}
          {/* TAB 3: RESUME MANAGEMENT TAB                                     */}
          {/* ───────────────────────────────────────────────────────────────── */}
          {activeTab === 'resume' && (
            <div className="max-w-3xl mx-auto space-y-6">
              <div className="bg-[#ffffff] rounded-2xl p-8 border border-[#d4dde8] shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-12 h-12 rounded-xl bg-[#cfe5ff] text-[#001d33] flex items-center justify-center">
                    <span className="material-symbols-outlined text-[28px]">description</span>
                  </div>
                  <div>
                    <h2 className="text-[20px] font-bold text-[#0f1c2b]">Candidate Master Resume</h2>
                    <p className="text-[13px] text-[#7a95b0]">Upload your latest PDF resume to update AI matching keywords and rubric extraction.</p>
                  </div>
                </div>

                <form onSubmit={handleResumeUpload} className="space-y-6">
                  <div className="border-2 border-dashed border-[#c1c7d1] rounded-2xl p-10 flex flex-col items-center justify-center text-center hover:bg-[#eef4ff]/50 hover:border-[#136299] transition-all cursor-pointer group">
                    <div className="w-14 h-14 rounded-full bg-[#cfe5ff] flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <span className="material-symbols-outlined text-[#001d33] text-[28px]">upload_file</span>
                    </div>
                    <label className="text-[14px] font-bold text-[#0f1c2b] mb-1 cursor-pointer">
                      Click to choose or drag and drop your PDF resume
                      <input
                        type="file"
                        accept=".pdf"
                        onChange={e => setResumeFile(e.target.files ? e.target.files[0] : null)}
                        className="hidden"
                      />
                    </label>
                    <p className="text-[12px] text-[#7a95b0]">PDF format up to 5MB</p>
                    {resumeFile && (
                      <div className="mt-4 px-4 py-2 bg-[#eefcf8] border border-[#8df5df] rounded-lg text-[#006b5c] text-[13px] font-semibold flex items-center gap-2">
                        <span className="material-symbols-outlined text-[18px]">check_circle</span>
                        Selected: {resumeFile.name} ({(resumeFile.size / 1024).toFixed(1)} KB)
                      </div>
                    )}
                  </div>

                  <div className="flex justify-end gap-3">
                    <button
                      type="submit"
                      disabled={!resumeFile || isUploadingResume}
                      className="btn-primary"
                    >
                      {isUploadingResume ? (
                        <>
                          <span className="material-symbols-outlined animate-spin text-[18px]">sync</span>
                          Uploading & Parsing...
                        </>
                      ) : (
                        <>
                          <span className="material-symbols-outlined text-[18px]">save</span>
                          Update Master Resume
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* ───────────────────────────────────────────────────────────────── */}
          {/* TAB 4: AGENT SETTINGS TAB                                        */}
          {/* ───────────────────────────────────────────────────────────────── */}
          {activeTab === 'settings' && (
            <div className="max-w-3xl mx-auto space-y-6">
              <div className="bg-[#ffffff] rounded-2xl p-8 border border-[#d4dde8] shadow-sm">
                <h2 className="text-[20px] font-bold text-[#0f1c2b] mb-6 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[#136299]">settings</span>
                  Autonomous System Configuration
                </h2>

                <div className="space-y-4">
                  <div className="p-4 bg-[#f8f9ff] rounded-xl border border-[#d4dde8]">
                    <div className="text-[11px] font-bold uppercase text-[#4a6080] mb-1">Groq LLM Engine Model</div>
                    <div className="text-[14px] font-semibold text-[#0f1c2b] font-mono">
                      {agentSettings?.groq_model || 'openai/gpt-oss-120b'}
                    </div>
                  </div>

                  <div className="p-4 bg-[#f8f9ff] rounded-xl border border-[#d4dde8]">
                    <div className="text-[11px] font-bold uppercase text-[#4a6080] mb-1">Recipient Email for CSV Reports</div>
                    <div className="text-[14px] font-semibold text-[#0f1c2b]">
                      {agentSettings?.recipient_email || 'manthanr141@gmail.com'}
                    </div>
                  </div>

                  <div className="p-4 bg-[#f8f9ff] rounded-xl border border-[#d4dde8]">
                    <div className="text-[11px] font-bold uppercase text-[#4a6080] mb-1">Twilio WhatsApp Alert Number</div>
                    <div className="text-[14px] font-semibold text-[#0f1c2b]">
                      {agentSettings?.user_whatsapp_number || '+919529883808'}
                    </div>
                  </div>

                  <div className="p-4 bg-[#f8f9ff] rounded-xl border border-[#d4dde8]">
                    <div className="text-[11px] font-bold uppercase text-[#4a6080] mb-1">Automated Cron Schedule</div>
                    <div className="flex items-center gap-2 text-[14px] font-semibold text-[#006b5c]">
                      <div className="pulse-dot"></div>
                      Runs twice daily at 9:00 AM IST & 9:00 PM IST (GitHub Actions + Local APScheduler)
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL 1: JOB DETAILS DRAWER                                         */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {selectedJob && (
        <div className="modal-backdrop" onClick={() => setSelectedJob(null)}>
          <div className="modal-card max-w-2xl max-h-[85vh] flex flex-col" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4 border-b border-[#d4dde8] pb-4">
              <div>
                <h3 className="text-[20px] font-bold text-[#0f1c2b] leading-tight mb-1">{selectedJob.title}</h3>
                <p className="text-[13px] text-[#4a6080]">
                  <span className="font-semibold text-[#0f1c2b]">{selectedJob.company}</span> • {selectedJob.location || 'Remote'}
                </p>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="text-[#717880] hover:text-[#0f1c2b] p-1 rounded-lg transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined text-[22px]">close</span>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {/* Match Score Box */}
              <div className="p-4 bg-[#eef4ff] rounded-xl border border-[#cfe5ff] flex items-center justify-between">
                <div>
                  <span className="text-[11px] font-bold text-[#004a77] uppercase tracking-wider">AI Match Fit</span>
                  <p className="text-[12px] text-[#41474f] mt-1">{selectedJob.match_reasoning || 'Strong fit with candidate skills.'}</p>
                </div>
                <div className="text-[24px] font-bold text-[#136299] shrink-0 pl-4">
                  {selectedJob.match_score ?? 0}/100
                </div>
              </div>

              {/* Full Description */}
              <div>
                <h4 className="text-[12px] font-bold uppercase text-[#4a6080] mb-2">Job Description</h4>
                <div className="text-[13px] text-[#0f1c2b] leading-relaxed whitespace-pre-wrap bg-[#f8f9ff] p-4 rounded-xl border border-[#d4dde8] max-h-64 overflow-y-auto">
                  {selectedJob.description}
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-[#d4dde8] flex items-center justify-end gap-3">
              <button
                onClick={() => handleJobAction(selectedJob.id, 'reject')}
                className="btn-secondary text-[#ba1a1a]"
              >
                <span className="material-symbols-outlined text-[16px]">close</span>
                Reject
              </button>

              <button
                onClick={() => handleJobAction(selectedJob.id, 'mark_applied')}
                className="btn-secondary text-[#006b5c]"
              >
                <span className="material-symbols-outlined text-[16px]">done</span>
                Mark Applied
              </button>

              <a
                href={selectedJob.apply_url || selectedJob.link}
                target="_blank"
                rel="noreferrer"
                className="btn-primary"
              >
                <span>Apply on {selectedJob.source}</span>
                <span className="material-symbols-outlined text-[16px]">open_in_new</span>
              </a>
            </div>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* MODAL 2: QUICK RESUME UPLOAD                                        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {isResumeModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsResumeModalOpen(false)}>
          <div className="modal-card max-w-md" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-[20px] font-bold text-[#0f1c2b]">Update Master Resume</h2>
              <button onClick={() => setIsResumeModalOpen(false)} className="text-[#717880] hover:text-[#0f1c2b]">
                <span className="material-symbols-outlined text-[22px]">close</span>
              </button>
            </div>

            <form onSubmit={handleResumeUpload}>
              <div className="border-2 border-dashed border-[#c1c7d1] rounded-xl p-8 flex flex-col items-center justify-center text-center hover:bg-[#eef4ff]/50 hover:border-[#136299] transition-all cursor-pointer group">
                <div className="w-12 h-12 rounded-full bg-[#cfe5ff] flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <span className="material-symbols-outlined text-[#001d33] text-[24px]">upload_file</span>
                </div>
                <label className="text-[13px] font-bold text-[#0f1c2b] mb-1 cursor-pointer">
                  Click to select PDF resume
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={e => setResumeFile(e.target.files ? e.target.files[0] : null)}
                    className="hidden"
                  />
                </label>
                <p className="text-[11px] text-[#7a95b0]">PDF up to 5MB</p>
                {resumeFile && (
                  <p className="mt-2 text-[12px] font-semibold text-[#006b5c]">{resumeFile.name}</p>
                )}
              </div>

              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setIsResumeModalOpen(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!resumeFile || isUploadingResume}
                  className="btn-primary"
                >
                  {isUploadingResume ? 'Uploading...' : 'Save Resume'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
