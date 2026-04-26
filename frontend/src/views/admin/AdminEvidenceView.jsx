import React from 'react';
import { Database, RefreshCw } from 'lucide-react';

const AdminEvidenceView = ({
  GlassCard,
  currentUser,
  sessions,
  analytics,
  slideSummary,
  loading,
  saving,
  error,
  onRefresh,
  onSeedSample,
}) => {
  const kpis = analytics?.kpis || {};
  const autoKpis = analytics?.auto_kpis || {};
  const sus = analytics?.sus || {};
  const autoSus = analytics?.auto_sus || {};
  const funnel = analytics?.funnel || {};
  const autoFunnel = analytics?.auto_funnel || {};
  const retention = analytics?.retention || {};
  const tasks = analytics?.tasks || [];
  const confusions = analytics?.friction?.top_confusion_tags || [];
  const quotes = analytics?.qualitative?.top_quotes || [];

  return (
    <div className="h-full overflow-y-auto pr-1 space-y-4">
      <div className="w-full max-w-6xl mx-auto space-y-4">
        <GlassCard className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">Internal Admin</p>
              <h2 className="text-2xl font-bold text-slate-900">Phase 4A Evidence Dashboard</h2>
              <p className="text-sm text-slate-600 mt-1">Logged in as {currentUser?.email || 'admin user'}.</p>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              type="button"
              onClick={onSeedSample}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-indigo-200 text-sm font-semibold text-indigo-700 hover:bg-indigo-50"
              disabled={saving}
            >
              <Database className="w-4 h-4" />
              Seed Sample Data
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </GlassCard>

        <section className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Users tested</p><p className="text-2xl font-bold">{kpis.users_tested || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Sessions</p><p className="text-2xl font-bold">{kpis.sessions_completed || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Avg duration (min)</p><p className="text-2xl font-bold">{kpis.avg_session_duration_minutes || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Avg SUS</p><p className="text-2xl font-bold">{kpis.avg_sus || 0}</p></GlassCard>
        </section>

        <section className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Live active users</p><p className="text-2xl font-bold">{autoKpis.active_users || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">Tracked events</p><p className="text-2xl font-bold">{autoKpis.events_tracked || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">In-app SUS responses</p><p className="text-2xl font-bold">{autoKpis.sus_responses || 0}</p></GlassCard>
          <GlassCard className="p-4"><p className="text-xs text-slate-500">In-app Avg SUS</p><p className="text-2xl font-bold">{autoKpis.auto_avg_sus || 0}</p></GlassCard>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Funnel</h3>
            <div className="mt-3 space-y-2">
              {Object.entries(funnel.counts || {}).map(([step, count]) => (
                <div key={step}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize">{step.replace('_', ' ')}</span>
                    <span>{count} ({funnel.conversion_percent?.[step] || 0}%)</span>
                  </div>
                  <div className="h-2 rounded bg-slate-100 mt-1">
                    <div className="h-2 rounded bg-indigo-500" style={{ width: `${Math.max(0, Math.min(100, funnel.conversion_percent?.[step] || 0))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">SUS Snapshot</h3>
            <p className="text-sm text-slate-600 mt-1">Min {sus.min || 0} / Max {sus.max || 0}</p>
            <div className="mt-3 space-y-2 text-sm">
              <p>Below 50: {sus.buckets?.below_50 || 0}</p>
              <p>50 to 68: {sus.buckets?.['50_to_68'] || 0}</p>
              <p>Above 68: {sus.buckets?.above_68 || 0}</p>
              <p>80+: {sus.buckets?.above_80 || 0}</p>
            </div>
            <p className="text-sm text-slate-600 mt-4">Live SUS: avg {autoSus.average || 0}, min {autoSus.min || 0}, max {autoSus.max || 0}</p>
          </GlassCard>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Live App Funnel</h3>
            <div className="mt-3 space-y-2">
              {Object.entries(autoFunnel.counts || {}).map(([step, count]) => (
                <div key={step}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize">{step.replace('_', ' ')}</span>
                    <span>{count} ({autoFunnel.conversion_percent?.[step] || 0}%)</span>
                  </div>
                  <div className="h-2 rounded bg-slate-100 mt-1">
                    <div className="h-2 rounded bg-emerald-500" style={{ width: `${Math.max(0, Math.min(100, autoFunnel.conversion_percent?.[step] || 0))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Retention (D1 / D7)</h3>
            <p className="text-sm text-slate-600 mt-1">Cohort size: {retention.cohort_size || 0} users</p>
            <div className="mt-3 space-y-2 text-sm">
              <p>D1 retained users: {retention.d1_users || 0}</p>
              <p>D1 retention rate: {retention.d1_rate || 0}%</p>
              <p>D7 retained users: {retention.d7_users || 0}</p>
              <p>D7 retention rate: {retention.d7_rate || 0}%</p>
            </div>
          </GlassCard>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Task Performance</h3>
            <div className="mt-2 space-y-2 max-h-64 overflow-y-auto">
              {tasks.length === 0 && <p className="text-sm text-slate-500">No task analytics yet.</p>}
              {tasks.map((task) => (
                <div key={task.task_id} className="rounded border border-slate-200 p-2 text-sm">
                  <p className="font-semibold">{task.task_id}</p>
                  <p>Completion: {task.completion_rate}% | Avg Time: {task.avg_time_seconds}s | Friction: {task.friction_index}</p>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Qualitative Signals</h3>
            <p className="text-sm text-slate-600 mt-1">Common confusion tags</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {confusions.map((item) => (
                <span key={item.tag} className="px-2 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-semibold">{item.tag} ({item.count})</span>
              ))}
            </div>
            <p className="text-sm text-slate-600 mt-4">Top quotes</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-700">
              {quotes.slice(0, 3).map((quote) => <li key={quote} className="border-l-2 border-indigo-300 pl-2">"{quote}"</li>)}
            </ul>
          </GlassCard>
        </section>

        <GlassCard className="p-4">
          <h3 className="text-lg font-semibold">Slide-Ready Summary</h3>
          <div className="mt-3 grid grid-cols-1 lg:grid-cols-2 gap-3 text-sm">
            <div className="rounded border border-slate-200 p-3">
              <p className="font-semibold">Who tested</p>
              <p className="mt-1">{slideSummary?.who_tested || 'No summary yet.'}</p>
            </div>
            <div className="rounded border border-slate-200 p-3">
              <p className="font-semibold">Top 3 insights</p>
              <ul className="list-disc ml-4 mt-1 space-y-1">
                {(slideSummary?.top_3_insights || []).map((item) => <li key={item}>{item}</li>)}
              </ul>
            </div>
          </div>
        </GlassCard>

        <GlassCard className="p-4">
          <h3 className="text-lg font-semibold">Manual Session Entry Removed</h3>
          <p className="text-sm text-slate-600 mt-2">
            This admin panel now focuses on automatically collected live behavioral metrics and in-app SUS responses from real user activity.
          </p>
        </GlassCard>
      </div>
    </div>
  );
};

export default AdminEvidenceView;
