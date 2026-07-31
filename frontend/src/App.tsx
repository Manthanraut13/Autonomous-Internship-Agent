import React, { useState, useEffect } from 'react';
import {
  Briefcase,
  CheckCircle2,
  Clock,
  XCircle,
  TrendingUp,
  Search,
  ExternalLink,
  Play,
  Settings,
  RefreshCw,
  Sparkles,
  Bot,
  Layers,
  Building2,
  X,
  AlertCircle,
  FileText
} from 'lucide-react';

interface ApplicationInfo {
  id: number;
  applied_at: string;
  status: string;
  link: string;
}

interface WhatsAppInfo {
  sent_at: string | null;
  user_approval: boolean | null;
  responded_at: string | null;
}

interface Job {
  id: number;
  job_id: string;
  title: string;
  company: string;
  description: string;
  link: string;
  source: string;
  scraped_at: string;
  updated_at: string;
  match_score: number | null;
  match_reasoning: string | null;
  status: string;
  application: ApplicationInfo | null;
  whatsapp: WhatsAppInfo | null;
}

interface Stats {
  total_jobs: number;
  applied_count: number;
  pending_count: number;
  rejected_count: number;
  avg_match_score: number;
  sources_distribution: Record<string, number>;
  status_distribution: Record<string, number>;
  recent_activity: any[];
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'crm' | 'analytics' | 'pipeline' | 'settings'>('crm');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [actionLoading, setActionLoading] = useState<boolean>(false);

  // Pipeline runner form
  const [pipelineQuery, setPipelineQuery] = useState<string>('software engineering intern');
  const [pipelineLimit, setPipelineLimit] = useState<number>(5);
  const [pipelineThreshold, setPipelineThreshold] = useState<number>(70);
  const [pipelineRunning, setPipelineRunning] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Agent Settings
  const [agentSettings, setAgentSettings] = useState<any>(null);

  // Fetch Stats & Jobs
  const fetchData = async () => {
    try {
      const [statsRes, jobsRes, settingsRes] = await Promise.all([
        fetch('/api/dashboard/stats'),
        fetch(`/api/dashboard/jobs?status=${statusFilter}&search=${encodeURIComponent(searchQuery)}&source=${sourceFilter}`),
        fetch('/api/dashboard/settings')
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }
      if (jobsRes.ok) {
        const jobsData = await jobsRes.json();
        setJobs(jobsData.jobs);
      }
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setAgentSettings(settingsData);
      }
    } catch (err) {
      console.error("Error fetching data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 6000);
    return () => clearInterval(interval);
  }, [statusFilter, searchQuery, sourceFilter]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Job Actions (Apply, Reject, Delete)
  const handleJobAction = async (jobId: number, action: 'apply' | 'reject' | 'delete') => {
    setActionLoading(true);
    try {
      const res = await fetch(`/api/dashboard/jobs/${jobId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message || `Action ${action} executed successfully`);
        fetchData();
        if (selectedJob && selectedJob.id === jobId) {
          if (action === 'delete') setSelectedJob(null);
          else setSelectedJob({ ...selectedJob, status: action === 'apply' ? 'applied' : 'rejected' });
        }
      } else {
        showToast(data.detail || "Action failed");
      }
    } catch (err) {
      showToast("Error connecting to server");
    } finally {
      setActionLoading(false);
    }
  };

  // Trigger Pipeline
  const handleRunPipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    setPipelineRunning(true);
    try {
      const res = await fetch('/api/dashboard/run-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: pipelineQuery,
          limit: pipelineLimit,
          threshold: pipelineThreshold
        })
      });
      const data = await res.json();
      if (res.ok) {
        showToast(data.message);
        setTimeout(fetchData, 2000);
      } else {
        showToast(data.detail || "Pipeline launch failed");
      }
    } catch (err) {
      showToast("Failed to launch pipeline");
    } finally {
      setPipelineRunning(false);
    }
  };

  const getSourceBadge = (source: string) => {
    const src = (source || 'web').toLowerCase();
    if (src.includes('indeed')) {
      return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20">Indeed</span>;
    }
    if (src.includes('linkedin')) {
      return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20">LinkedIn</span>;
    }
    if (src.includes('remotive')) {
      return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">Remotive</span>;
    }
    return <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">{source}</span>;
  };

  const getStatusBadge = (status: string) => {
    const st = (status || '').toLowerCase();
    if (st === 'applied') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 glow-emerald">
          <CheckCircle2 className="w-3.5 h-3.5" /> Applied
        </span>
      );
    }
    if (st === 'pending' || st === 'approved') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/30">
          <Clock className="w-3.5 h-3.5" /> Pending Approval
        </span>
      );
    }
    if (st === 'rejected') {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-full bg-rose-500/15 text-rose-400 border border-rose-500/30">
          <XCircle className="w-3.5 h-3.5" /> Rejected
        </span>
      );
    }
    return <span className="px-3 py-1 text-xs font-medium rounded-full bg-slate-800 text-slate-400">{status}</span>;
  };

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-slate-500';
    if (score >= 80) return 'text-emerald-400';
    if (score >= 60) return 'text-amber-400';
    return 'text-rose-400';
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-slate-100 font-sans flex flex-col">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 px-4 py-3 bg-slate-900/90 border border-indigo-500/40 text-indigo-200 rounded-xl shadow-2xl backdrop-blur-md animate-bounce">
          <Sparkles className="w-5 h-5 text-indigo-400" />
          <span className="text-sm font-medium">{toastMessage}</span>
        </div>
      )}

      {/* Top Header Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold bg-gradient-to-r from-white via-slate-200 to-indigo-300 bg-clip-text text-transparent">
                  Autonomous Internship Agent
                </h1>
                <span className="flex h-2 w-2 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
              </div>
              <p className="text-xs text-slate-400">Agent CRM & Autonomous Operations Portal</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-slate-900/80 p-1.5 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTab('crm')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'crm'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Briefcase className="w-4 h-4" /> CRM Jobs
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'analytics'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <TrendingUp className="w-4 h-4" /> Analytics
            </button>
            <button
              onClick={() => setActiveTab('pipeline')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'pipeline'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Play className="w-4 h-4" /> Pipeline Control
            </button>
            <button
              onClick={() => setActiveTab('settings')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'settings'
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`}
            >
              <Settings className="w-4 h-4" /> Settings & Resume
            </button>
          </nav>

          {/* Quick Actions */}
          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              className="p-2.5 rounded-xl border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-all"
              title="Refresh Data"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* KPI Analytics Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="glass-panel p-5 rounded-2xl flex flex-col justify-between glass-panel-hover">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold tracking-wider uppercase">Total Processed</span>
                <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center text-indigo-400">
                  <Layers className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-white">{stats.total_jobs}</div>
              <p className="text-xs text-slate-500 mt-2">Discovered & evaluated</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl flex flex-col justify-between glass-panel-hover border-emerald-500/20">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold tracking-wider uppercase text-emerald-400">Applied</span>
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-emerald-400">{stats.applied_count}</div>
              <p className="text-xs text-slate-500 mt-2">Auto-submitted applications</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl flex flex-col justify-between glass-panel-hover border-amber-500/20">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold tracking-wider uppercase text-amber-400">Pending Approval</span>
                <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-400">
                  <Clock className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-amber-400">{stats.pending_count}</div>
              <p className="text-xs text-slate-500 mt-2">1-by-1 WhatsApp Queue</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl flex flex-col justify-between glass-panel-hover border-rose-500/20">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold tracking-wider uppercase text-rose-400">Rejected</span>
                <div className="w-8 h-8 rounded-lg bg-rose-500/10 flex items-center justify-center text-rose-400">
                  <XCircle className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-rose-400">{stats.rejected_count}</div>
              <p className="text-xs text-slate-500 mt-2">Declined by user</p>
            </div>

            <div className="glass-panel p-5 rounded-2xl flex flex-col justify-between glass-panel-hover">
              <div className="flex items-center justify-between text-slate-400 mb-2">
                <span className="text-xs font-semibold tracking-wider uppercase">Avg Match Score</span>
                <div className="w-8 h-8 rounded-lg bg-violet-500/10 flex items-center justify-center text-violet-400">
                  <Sparkles className="w-4 h-4" />
                </div>
              </div>
              <div className="text-3xl font-extrabold text-violet-400">{stats.avg_match_score}<span className="text-lg font-normal text-slate-500">/100</span></div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden mt-2">
                <div className="bg-gradient-to-r from-indigo-500 to-emerald-400 h-full rounded-full" style={{ width: `${stats.avg_match_score}%` }}></div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 1: CRM JOBS TABLE */}
        {activeTab === 'crm' && (
          <div className="space-y-6">
            {/* Filter Bar */}
            <div className="glass-panel p-4 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
              {/* Status Filter Tabs */}
              <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto p-1 bg-slate-950/60 rounded-xl border border-slate-800">
                {['all', 'pending', 'applied', 'rejected'].map((st) => (
                  <button
                    key={st}
                    onClick={() => setStatusFilter(st)}
                    className={`px-4 py-2 text-xs font-semibold rounded-lg capitalize transition-all whitespace-nowrap ${
                      statusFilter === st
                        ? 'bg-indigo-600 text-white shadow-md'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {st === 'pending' ? 'Pending Approval' : st}
                  </button>
                ))}
              </div>

              {/* Search & Source Filter */}
              <div className="flex items-center gap-3 w-full md:w-auto">
                <div className="relative flex-1 md:w-64">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search title, company..."
                    className="w-full bg-slate-950/80 border border-slate-800 text-sm text-slate-200 placeholder-slate-500 pl-9 pr-4 py-2 rounded-xl focus:outline-none focus:border-indigo-500/50"
                  />
                </div>

                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="bg-slate-950/80 border border-slate-800 text-sm text-slate-300 px-3 py-2 rounded-xl focus:outline-none focus:border-indigo-500/50"
                >
                  <option value="all">All Sources</option>
                  <option value="indeed">Indeed</option>
                  <option value="linkedin">LinkedIn</option>
                  <option value="remotive">Remotive</option>
                </select>
              </div>
            </div>

            {/* Jobs Table */}
            <div className="glass-panel rounded-2xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 bg-slate-950/40 text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      <th className="py-4 px-6">Job Title & Company</th>
                      <th className="py-4 px-6">Source</th>
                      <th className="py-4 px-6">Match Score</th>
                      <th className="py-4 px-6">Status</th>
                      <th className="py-4 px-6">Scraped Date</th>
                      <th className="py-4 px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-sm text-slate-300">
                    {jobs.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="py-12 text-center text-slate-500">
                          <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                          No job listings found matching your filters.
                        </td>
                      </tr>
                    ) : (
                      jobs.map((j) => (
                        <tr key={j.id} className="hover:bg-slate-800/40 transition-colors">
                          <td className="py-4 px-6">
                            <div className="font-semibold text-slate-100 flex items-center gap-2">
                              {j.title}
                              <a
                                href={j.link}
                                target="_blank"
                                rel="noreferrer"
                                className="text-slate-500 hover:text-indigo-400"
                                title="Open Job Post"
                              >
                                <ExternalLink className="w-3.5 h-3.5" />
                              </a>
                            </div>
                            <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
                              <Building2 className="w-3 h-3 text-slate-500" /> {j.company}
                            </div>
                          </td>

                          <td className="py-4 px-6">
                            {getSourceBadge(j.source)}
                          </td>

                          <td className="py-4 px-6">
                            <div className="flex items-center gap-2">
                              <span className={`font-bold ${getScoreColor(j.match_score)}`}>
                                {j.match_score !== null ? `${j.match_score}/100` : 'N/A'}
                              </span>
                              {j.match_score !== null && (
                                <div className="w-16 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full ${j.match_score >= 80 ? 'bg-emerald-400' : j.match_score >= 60 ? 'bg-amber-400' : 'bg-rose-400'}`}
                                    style={{ width: `${j.match_score}%` }}
                                  ></div>
                                </div>
                              )}
                            </div>
                          </td>

                          <td className="py-4 px-6">
                            {getStatusBadge(j.status)}
                          </td>

                          <td className="py-4 px-6 text-xs text-slate-400">
                            {j.scraped_at ? new Date(j.scraped_at).toLocaleDateString() : 'N/A'}
                          </td>

                          <td className="py-4 px-6 text-right space-x-2">
                            <button
                              onClick={() => setSelectedJob(j)}
                              className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 text-slate-200 hover:bg-slate-700 transition-all"
                            >
                              Inspect
                            </button>

                            {j.status !== 'applied' && (
                              <button
                                onClick={() => handleJobAction(j.id, 'apply')}
                                disabled={actionLoading}
                                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-600/40 transition-all"
                              >
                                Auto-Apply
                              </button>
                            )}

                            {j.status !== 'rejected' && j.status !== 'applied' && (
                              <button
                                onClick={() => handleJobAction(j.id, 'reject')}
                                disabled={actionLoading}
                                className="px-3 py-1.5 text-xs font-medium rounded-lg bg-rose-600/10 text-rose-400 hover:bg-rose-600/30 transition-all"
                              >
                                Reject
                              </button>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: ANALYTICS */}
        {activeTab === 'analytics' && stats && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-panel p-6 rounded-2xl space-y-6">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-indigo-400" /> Job Source Breakdown
              </h2>
              <div className="space-y-4">
                {Object.entries(stats.sources_distribution).map(([source, count]) => (
                  <div key={source} className="space-y-1.5">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium text-slate-300 capitalize">{source}</span>
                      <span className="text-slate-400">{count} jobs ({Math.round((count / stats.total_jobs) * 100 || 0)}%)</span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div
                        className="bg-indigo-500 h-full rounded-full"
                        style={{ width: `${(count / stats.total_jobs) * 100 || 0}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl space-y-6">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Clock className="w-5 h-5 text-indigo-400" /> Recent Operations Timeline
              </h2>
              <div className="space-y-3">
                {stats.recent_activity.map((act) => (
                  <div key={act.id} className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-slate-200">{act.title}</div>
                      <div className="text-xs text-slate-400">{act.company}</div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-bold text-violet-400">{act.match_score}/100</span>
                      {getStatusBadge(act.status)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB 3: PIPELINE CONTROL */}
        {activeTab === 'pipeline' && (
          <div className="max-w-2xl mx-auto glass-panel p-8 rounded-2xl space-y-6">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400">
                <Play className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Pipeline Execution Controller</h2>
                <p className="text-xs text-slate-400">Trigger real-time job scraping, LLM matching & WhatsApp prompt dispatch</p>
              </div>
            </div>

            <form onSubmit={handleRunPipeline} className="space-y-5">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Job Search Keywords</label>
                <input
                  type="text"
                  value={pipelineQuery}
                  onChange={(e) => setPipelineQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 text-sm text-slate-100 p-3 rounded-xl focus:outline-none focus:border-indigo-500"
                  placeholder="e.g. software engineer, python developer"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Max Jobs Limit</label>
                  <input
                    type="number"
                    value={pipelineLimit}
                    onChange={(e) => setPipelineLimit(Number(e.target.value))}
                    min={1}
                    max={20}
                    className="w-full bg-slate-950 border border-slate-800 text-sm text-slate-100 p-3 rounded-xl focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase mb-2">Match Threshold Score</label>
                  <input
                    type="number"
                    value={pipelineThreshold}
                    onChange={(e) => setPipelineThreshold(Number(e.target.value))}
                    min={0}
                    max={100}
                    className="w-full bg-slate-950 border border-slate-800 text-sm text-slate-100 p-3 rounded-xl focus:outline-none focus:border-indigo-500"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={pipelineRunning}
                className="w-full py-3.5 px-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-semibold rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {pipelineRunning ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" /> Launching Pipeline...
                  </>
                ) : (
                  <>
                    <Play className="w-5 h-5 fill-current" /> Execute Agent Search Pipeline
                  </>
                )}
              </button>
            </form>
          </div>
        )}

        {/* TAB 4: SETTINGS & RESUME */}
        {activeTab === 'settings' && agentSettings && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="glass-panel p-6 rounded-2xl space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Settings className="w-5 h-5 text-indigo-400" /> Agent Settings & Configuration
              </h2>
              <div className="space-y-3 text-sm text-slate-300">
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Groq LLM Model</span>
                  <span className="font-semibold text-indigo-400">{agentSettings.groq_model}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Recipient WhatsApp Phone</span>
                  <span className="font-semibold text-slate-200">{agentSettings.user_whatsapp_number}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Twilio Sender Number</span>
                  <span className="font-semibold text-slate-200">{agentSettings.twilio_phone_number}</span>
                </div>
                <div className="flex justify-between py-2 border-b border-slate-800">
                  <span className="text-slate-400">Default Match Threshold</span>
                  <span className="font-semibold text-emerald-400">{agentSettings.match_score_threshold}/100</span>
                </div>
                <div className="flex justify-between py-2">
                  <span className="text-slate-400">Active Job Sources</span>
                  <span className="font-semibold text-slate-200 capitalize">{Array.isArray(agentSettings.job_sources) ? agentSettings.job_sources.join(', ') : agentSettings.job_sources}</span>
                </div>
              </div>
            </div>

            <div className="glass-panel p-6 rounded-2xl space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-indigo-400" /> Active Candidate Resume
              </h2>
              <div className="p-4 bg-slate-950/60 rounded-xl border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-indigo-400" />
                  <div>
                    <div className="text-sm font-semibold text-white">Manthan_Raut_Resume (1).pdf</div>
                    <div className="text-xs text-slate-400">Active PDF for auto-apply automation</div>
                  </div>
                </div>
                <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Active
                </span>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* INSPECT JOB MODAL / DRAWER */}
      {selectedJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fadeIn">
          <div className="glass-panel w-full max-w-2xl max-h-[90vh] rounded-3xl overflow-hidden flex flex-col shadow-2xl border-slate-700/50">
            <div className="p-6 border-b border-slate-800 flex items-start justify-between bg-slate-950/40">
              <div>
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  {selectedJob.title}
                  <a href={selectedJob.link} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-indigo-400">
                    <ExternalLink className="w-4 h-4" />
                  </a>
                </h2>
                <div className="text-sm text-slate-400 flex items-center gap-2 mt-1">
                  <Building2 className="w-4 h-4 text-slate-500" /> {selectedJob.company} • {getSourceBadge(selectedJob.source)}
                </div>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-sm text-slate-300">
              {/* Match Score & Reasoning */}
              <div className="p-4 bg-slate-950/60 rounded-2xl border border-slate-800/80 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Groq LLM Evaluation Score</span>
                  <span className={`text-lg font-bold ${getScoreColor(selectedJob.match_score)}`}>
                    {selectedJob.match_score !== null ? `${selectedJob.match_score}/100` : 'N/A'}
                  </span>
                </div>
                {selectedJob.match_reasoning && (
                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-900/80 p-3 rounded-xl border border-slate-800">
                    {selectedJob.match_reasoning}
                  </p>
                )}
              </div>

              {/* Status & Timestamps */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500 mb-1">Current Status</div>
                  <div>{getStatusBadge(selectedJob.status)}</div>
                </div>
                <div className="p-3 bg-slate-950/40 rounded-xl border border-slate-800">
                  <div className="text-xs text-slate-500 mb-1">Scraped Timestamp</div>
                  <div className="text-xs text-slate-300">{selectedJob.scraped_at ? new Date(selectedJob.scraped_at).toLocaleString() : 'N/A'}</div>
                </div>
              </div>

              {/* Description */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Job Description</h3>
                <div className="p-4 bg-slate-950/60 rounded-2xl border border-slate-800 text-xs leading-relaxed max-h-48 overflow-y-auto">
                  {selectedJob.description || 'No description available.'}
                </div>
              </div>
            </div>

            {/* Footer Actions */}
            <div className="p-6 border-t border-slate-800 bg-slate-950/40 flex items-center justify-between">
              <button
                onClick={() => handleJobAction(selectedJob.id, 'delete')}
                disabled={actionLoading}
                className="px-4 py-2 text-xs font-semibold text-rose-400 hover:bg-rose-600/10 rounded-xl transition-all"
              >
                Delete Record
              </button>

              <div className="flex items-center gap-3">
                {selectedJob.status !== 'rejected' && (
                  <button
                    onClick={() => handleJobAction(selectedJob.id, 'reject')}
                    disabled={actionLoading}
                    className="px-4 py-2 text-xs font-semibold text-slate-300 bg-slate-800 hover:bg-slate-700 rounded-xl transition-all"
                  >
                    Reject Job
                  </button>
                )}

                {selectedJob.status !== 'applied' && (
                  <button
                    onClick={() => handleJobAction(selectedJob.id, 'apply')}
                    disabled={actionLoading}
                    className="px-4 py-2 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-500 rounded-xl shadow-lg shadow-emerald-600/30 transition-all flex items-center gap-2"
                  >
                    <CheckCircle2 className="w-4 h-4" /> Trigger Auto-Apply
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
