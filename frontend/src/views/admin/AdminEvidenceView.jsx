import React, { useMemo, useState } from 'react';
import { Database, RefreshCw, Save } from 'lucide-react';

const DEFAULT_TASKS = [
  { task_id: 'upload_prescription', completed: false, time_seconds: 0, hesitations_count: 0, confusion_tags: '' },
  { task_id: 'add_medication', completed: false, time_seconds: 0, hesitations_count: 0, confusion_tags: '' },
  { task_id: 'open_safety_report', completed: false, time_seconds: 0, hesitations_count: 0, confusion_tags: '' },
];

const DEFAULT_FORM = {
  tester_label: '',
  segment: '',
  session_date: '',
  duration_minutes: 0,
  consent: false,
  funnel: {
    started: true,
    uploaded_prescription: false,
    added_med: false,
    opened_safety: false,
    finished: false,
  },
  tasks: DEFAULT_TASKS,
  sus_responses: Array(10).fill(3),
  reflection: {
    useful: '',
    confusing: '',
    would_use_again: '',
    would_pay: '',
    notes: '',
    top_quote: '',
  },
};

const toForm = (session) => {
  if (!session) return DEFAULT_FORM;
  return {
    tester_label: session.tester_label || '',
    segment: session.segment || '',
    session_date: session.session_date || '',
    duration_minutes: Number(session.duration_minutes || 0),
    consent: Boolean(session.consent),
    funnel: {
      started: Boolean(session.funnel?.started),
      uploaded_prescription: Boolean(session.funnel?.uploaded_prescription),
      added_med: Boolean(session.funnel?.added_med),
      opened_safety: Boolean(session.funnel?.opened_safety),
      finished: Boolean(session.funnel?.finished),
    },
    tasks: Array.isArray(session.tasks) && session.tasks.length > 0
      ? session.tasks.map((task) => ({
        task_id: task.task_id || 'task',
        completed: Boolean(task.completed),
        time_seconds: Number(task.time_seconds || 0),
        hesitations_count: Number(task.hesitations_count || 0),
        confusion_tags: Array.isArray(task.confusion_tags) ? task.confusion_tags.join(', ') : '',
      }))
      : DEFAULT_TASKS,
    sus_responses: Array.isArray(session.sus_responses) && session.sus_responses.length === 10
      ? session.sus_responses.map((value) => Number(value || 3))
      : Array(10).fill(3),
    reflection: {
      useful: session.reflection?.useful || '',
      confusing: session.reflection?.confusing || '',
      would_use_again: session.reflection?.would_use_again || '',
      would_pay: session.reflection?.would_pay || '',
      notes: session.reflection?.notes || '',
      top_quote: session.reflection?.top_quote || '',
    },
  };
};

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
  onCreateSession,
  onUpdateSession,
  onSeedSample,
}) => {
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [form, setForm] = useState(DEFAULT_FORM);

  const selectedSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) || null,
    [sessions, selectedSessionId],
  );

  const resetForm = () => {
    setSelectedSessionId('');
    setForm(DEFAULT_FORM);
  };

  const loadSession = (sessionId) => {
    setSelectedSessionId(sessionId);
    const candidate = sessions.find((item) => item.id === sessionId) || null;
    setForm(toForm(candidate));
  };

  const handleTaskChange = (idx, key, value) => {
    setForm((prev) => {
      const next = [...prev.tasks];
      next[idx] = { ...next[idx], [key]: value };
      return { ...prev, tasks: next };
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const payload = {
      ...form,
      tasks: form.tasks.map((task) => ({
        ...task,
        time_seconds: Number(task.time_seconds || 0),
        hesitations_count: Number(task.hesitations_count || 0),
        confusion_tags: String(task.confusion_tags || '')
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      })),
      sus_responses: form.sus_responses.map((value) => Number(value || 3)),
      duration_minutes: Number(form.duration_minutes || 0),
    };
    if (selectedSessionId) {
      await onUpdateSession(selectedSessionId, payload);
    } else {
      await onCreateSession(payload);
    }
    resetForm();
  };

  const kpis = analytics?.kpis || {};
  const sus = analytics?.sus || {};
  const funnel = analytics?.funnel || {};
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
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">{selectedSession ? 'Edit Session' : 'Add Test Session'}</h3>
            <div className="flex items-center gap-2">
              <select
                value={selectedSessionId}
                onChange={(e) => (e.target.value ? loadSession(e.target.value) : resetForm())}
                className="px-2 py-1 text-sm rounded border border-slate-300"
              >
                <option value="">New session</option>
                {sessions.map((session) => (
                  <option value={session.id} key={session.id}>{session.tester_label} ({session.session_date || 'n/a'})</option>
                ))}
              </select>
              {selectedSessionId && (
                <button type="button" onClick={resetForm} className="px-2 py-1 text-xs rounded border border-slate-300">Clear</button>
              )}
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
              <input value={form.tester_label} onChange={(e) => setForm((p) => ({ ...p, tester_label: e.target.value }))} placeholder="Tester label" className="px-3 py-2 rounded border border-slate-300 text-sm" required />
              <input value={form.segment} onChange={(e) => setForm((p) => ({ ...p, segment: e.target.value }))} placeholder="Segment" className="px-3 py-2 rounded border border-slate-300 text-sm" />
              <input value={form.session_date} onChange={(e) => setForm((p) => ({ ...p, session_date: e.target.value }))} placeholder="Session date (YYYY-MM-DD)" className="px-3 py-2 rounded border border-slate-300 text-sm" />
              <input type="number" min="0" value={form.duration_minutes} onChange={(e) => setForm((p) => ({ ...p, duration_minutes: Number(e.target.value || 0) }))} placeholder="Duration minutes" className="px-3 py-2 rounded border border-slate-300 text-sm" />
            </div>

            <div className="rounded border border-slate-200 p-3">
              <p className="font-semibold text-sm mb-2">Funnel steps</p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {Object.keys(form.funnel).map((key) => (
                  <label key={key} className="text-xs flex items-center gap-2">
                    <input type="checkbox" checked={form.funnel[key]} onChange={(e) => setForm((p) => ({ ...p, funnel: { ...p.funnel, [key]: e.target.checked } }))} />
                    {key.replace('_', ' ')}
                  </label>
                ))}
              </div>
            </div>

            <div className="rounded border border-slate-200 p-3">
              <p className="font-semibold text-sm mb-2">Tasks</p>
              <div className="space-y-2">
                {form.tasks.map((task, idx) => (
                  <div key={`${task.task_id}-${idx}`} className="grid grid-cols-1 md:grid-cols-5 gap-2 items-center">
                    <input value={task.task_id} onChange={(e) => handleTaskChange(idx, 'task_id', e.target.value)} className="px-2 py-1 rounded border border-slate-300 text-sm" />
                    <label className="text-xs flex items-center gap-2"><input type="checkbox" checked={task.completed} onChange={(e) => handleTaskChange(idx, 'completed', e.target.checked)} /> Completed</label>
                    <input type="number" min="0" value={task.time_seconds} onChange={(e) => handleTaskChange(idx, 'time_seconds', Number(e.target.value || 0))} placeholder="Time sec" className="px-2 py-1 rounded border border-slate-300 text-sm" />
                    <input type="number" min="0" value={task.hesitations_count} onChange={(e) => handleTaskChange(idx, 'hesitations_count', Number(e.target.value || 0))} placeholder="Hesitations" className="px-2 py-1 rounded border border-slate-300 text-sm" />
                    <input value={task.confusion_tags} onChange={(e) => handleTaskChange(idx, 'confusion_tags', e.target.value)} placeholder="Tags: upload,form" className="px-2 py-1 rounded border border-slate-300 text-sm" />
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded border border-slate-200 p-3">
              <p className="font-semibold text-sm mb-2">SUS responses (1-5)</p>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {form.sus_responses.map((value, idx) => (
                  <label key={`sus-${idx}`} className="text-xs">
                    Q{idx + 1}
                    <input
                      type="number"
                      min="1"
                      max="5"
                      value={value}
                      onChange={(e) => {
                        const next = [...form.sus_responses];
                        next[idx] = Number(e.target.value || 3);
                        setForm((prev) => ({ ...prev, sus_responses: next }));
                      }}
                      className="w-full mt-1 px-2 py-1 rounded border border-slate-300 text-sm"
                    />
                  </label>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <textarea value={form.reflection.useful} onChange={(e) => setForm((p) => ({ ...p, reflection: { ...p.reflection, useful: e.target.value } }))} placeholder="What did user find useful?" className="px-3 py-2 rounded border border-slate-300 text-sm min-h-20" />
              <textarea value={form.reflection.confusing} onChange={(e) => setForm((p) => ({ ...p, reflection: { ...p.reflection, confusing: e.target.value } }))} placeholder="What was confusing?" className="px-3 py-2 rounded border border-slate-300 text-sm min-h-20" />
              <textarea value={form.reflection.would_use_again} onChange={(e) => setForm((p) => ({ ...p, reflection: { ...p.reflection, would_use_again: e.target.value } }))} placeholder="Would use again? Why?" className="px-3 py-2 rounded border border-slate-300 text-sm min-h-20" />
              <textarea value={form.reflection.would_pay} onChange={(e) => setForm((p) => ({ ...p, reflection: { ...p.reflection, would_pay: e.target.value } }))} placeholder="Would pay? Why/why not?" className="px-3 py-2 rounded border border-slate-300 text-sm min-h-20" />
            </div>
            <textarea value={form.reflection.top_quote} onChange={(e) => setForm((p) => ({ ...p, reflection: { ...p.reflection, top_quote: e.target.value } }))} placeholder="Top quote from participant" className="px-3 py-2 rounded border border-slate-300 text-sm w-full min-h-16" />
            <label className="text-sm flex items-center gap-2"><input type="checkbox" checked={form.consent} onChange={(e) => setForm((p) => ({ ...p, consent: e.target.checked }))} /> Participant consented to testing notes.</label>

            <button type="submit" disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold disabled:opacity-60">
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : (selectedSession ? 'Update session' : 'Save session')}
            </button>
          </form>
        </GlassCard>
      </div>
    </div>
  );
};

export default AdminEvidenceView;
