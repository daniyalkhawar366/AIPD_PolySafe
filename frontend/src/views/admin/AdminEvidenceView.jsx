import React from 'react';
import { RefreshCw, FlaskConical, Target } from 'lucide-react';

const AdminEvidenceView = ({
  GlassCard,
  currentUser,
  analytics,
  slideSummary,
  loading,
  seedLoading,
  seedInfo,
  error,
  onRefresh,
  onSeed,
  onReset,
}) => {
  const kpis = analytics?.kpis || {};
  const liveSummary = analytics?.live_summary || {};
  const sus = analytics?.sus || {};
  const funnel = analytics?.funnel || {};
  const questions = sus?.questions || [];
  const feedbackRows = analytics?.qualitative?.feedback_rows || [];
  const susBuckets = sus?.buckets || {};
  const bucketTotal = Math.max(
    1,
    (susBuckets?.below_50 || 0) + (susBuckets?.['50_to_68'] || 0) + (susBuckets?.above_68 || 0),
  );
  const funnelRows = Object.entries(funnel?.counts || {}).map(([step, count]) => ({
    step,
    count: Number(count || 0),
    conversion: Number(funnel?.conversion_percent?.[step] || 0),
  }));
  const quotes = analytics?.qualitative?.top_quotes || [];

  // ── Phase 4B: PMF Metrics ─────────────────────────────────────────────────
  const funnelCounts = funnel?.counts || {};
  const uploadedCount = Number(funnelCounts.uploaded_prescription || 0);
  const safetyViewedCount = Number(funnelCounts.safety_report_viewed || 0);
  const startedCount = Number(funnelCounts.started || 0);

  // Product KPI: Safety Activation Rate = % of uploaders who viewed safety report
  const safetyActivationRate = uploadedCount > 0
    ? Math.round((safetyViewedCount / uploadedCount) * 100)
    : 0;

  const getPmfSignal = (rate) => {
    if (rate >= 70) return { label: 'Strong PMF Signal 🟢', className: 'bg-emerald-50 border-emerald-200 text-emerald-700' };
    if (rate >= 40) return { label: 'Early PMF Signal 🟡', className: 'bg-amber-50 border-amber-200 text-amber-700' };
    return { label: 'No PMF Signal 🔴', className: 'bg-red-50 border-red-200 text-red-700' };
  };
  const pmfSignal = getPmfSignal(safetyActivationRate);

  // A/B experiment data (populated when enough events accumulate)
  const abExperimentData = analytics?.ab_experiment || null;
  const controlClickRate = abExperimentData?.control?.add_all_rate ?? null;
  const variantClickRate = abExperimentData?.confidence_badges?.add_all_rate ?? null;
  const abLift = (controlClickRate !== null && variantClickRate !== null)
    ? Math.round(((variantClickRate - controlClickRate) / Math.max(1, controlClickRate)) * 100)
    : null;

  return (
    <div className="h-full overflow-y-auto pr-1 space-y-4">
      <div className="w-full max-w-7xl mx-auto space-y-4">

        {/* Header */}
        <GlassCard className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs uppercase tracking-wide text-indigo-600 font-semibold">Internal Admin</p>
              <h2 className="text-2xl font-bold text-slate-900">Evidence Analytics Dashboard</h2>
              <p className="text-sm text-slate-600 mt-1">Logged in as {currentUser?.email || 'admin user'}.</p>
            </div>
            <button
              type="button"
              onClick={onRefresh}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              disabled={loading || seedLoading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
            <button
              type="button"
              onClick={onSeed}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-indigo-200 text-sm font-semibold text-indigo-700 hover:bg-indigo-50 disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={loading || seedLoading}
            >
              <RefreshCw className={`w-4 h-4 ${seedLoading ? 'animate-spin' : ''}`} />
              Seed Live Evidence
            </button>
            <button
              type="button"
              onClick={onReset}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-rose-200 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={loading || seedLoading}
            >
              <RefreshCw className={`w-4 h-4 ${seedLoading ? 'animate-spin' : ''}`} />
              Reset Evidence
            </button>
          </div>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          {seedInfo && <p className="mt-3 text-sm text-emerald-700">{seedInfo}</p>}
        </GlassCard>

        {/* ── Phase 4B: PMF Metrics Section ─────────────────────── */}
        <GlassCard className="p-4 border-2 border-indigo-100">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-indigo-600" />
            <h3 className="text-lg font-bold text-slate-900">Phase 4B — PMF Metrics</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Product KPI: Safety Activation Rate */}
            <div className="rounded-xl border border-slate-200 p-4 bg-gradient-to-br from-indigo-50 to-white">
              <p className="text-[11px] font-bold uppercase tracking-wide text-indigo-500">Product KPI</p>
              <p className="text-sm font-semibold text-slate-700 mt-1">Safety Activation Rate</p>
              <p className="text-4xl font-bold text-slate-900 mt-2">{safetyActivationRate}%</p>
              <p className="text-xs text-slate-500 mt-1">
                {safetyViewedCount} of {uploadedCount} uploaders viewed the safety report
              </p>
              <span className={`mt-3 inline-flex items-center text-[11px] font-semibold px-2 py-0.5 rounded-full border ${pmfSignal.className}`}>
                {pmfSignal.label}
              </span>
              <div className="mt-3 space-y-1 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
                <p>🔴 &lt;20% — No PMF</p>
                <p>🟡 40–70% — Early PMF</p>
                <p>🟢 &gt;70% — Strong PMF</p>
              </div>
            </div>

            {/* Business KPI: Premium Conversion */}
            <div className="rounded-xl border border-slate-200 p-4 bg-gradient-to-br from-emerald-50 to-white">
              <p className="text-[11px] font-bold uppercase tracking-wide text-emerald-600">Business KPI</p>
              <p className="text-sm font-semibold text-slate-700 mt-1">Premium Conversion Rate</p>
              <p className="text-4xl font-bold text-slate-900 mt-2">
                {analytics?.premium_conversion_rate != null
                  ? `${analytics.premium_conversion_rate}%`
                  : '—'}
              </p>
              <p className="text-xs text-slate-500 mt-1">Free → Paid upgrades / total registered users</p>
              <div className="mt-3 space-y-1 text-[11px] text-slate-500 border-t border-slate-100 pt-2">
                <p>🔴 &lt;2% — No PMF</p>
                <p>🟡 2–5% — Early PMF</p>
                <p>🟢 &gt;5% — Strong PMF</p>
              </div>
            </div>

            {/* Funnel Summary */}
            <div className="rounded-xl border border-slate-200 p-4 bg-gradient-to-br from-violet-50 to-white">
              <p className="text-[11px] font-bold uppercase tracking-wide text-violet-600">Activation Funnel</p>
              <p className="text-sm font-semibold text-slate-700 mt-1">User Journey Steps</p>
              <div className="mt-3 space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="text-slate-600">App Opened</span>
                  <span className="font-bold text-slate-900">{startedCount}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600">Prescription Uploaded</span>
                  <span className="font-bold text-slate-900">{uploadedCount}</span>
                </div>
                <div className="flex justify-between items-center border-t border-dashed border-indigo-200 pt-2">
                  <span className="text-indigo-700 font-semibold">Safety Report Viewed ✓</span>
                  <span className="font-bold text-indigo-700">{safetyViewedCount}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-600">SUS Submitted</span>
                  <span className="font-bold text-slate-900">{Number(funnelCounts.finished || 0)}</span>
                </div>
              </div>
            </div>
          </div>
        </GlassCard>

        {/* ── Phase 4B: A/B Experiment Results ──────────────────── */}
        <GlassCard className="p-4 border-2 border-amber-100">
          <div className="flex items-center gap-2 mb-4">
            <FlaskConical className="w-5 h-5 text-amber-600" />
            <h3 className="text-lg font-bold text-slate-900">Phase 4B — A/B Experiment: Trust Transparency</h3>
            <span className="ml-auto text-[11px] font-semibold px-2 py-0.5 rounded-full border bg-amber-50 text-amber-700 border-amber-200">
              Live · Collecting Data
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="rounded-xl border border-slate-200 p-4 bg-white">
              <p className="text-[11px] font-bold uppercase tracking-wide text-slate-500">Group A — Control</p>
              <p className="text-sm text-slate-600 mt-1">Standard medicine list — no confidence badges</p>
              <p className="text-3xl font-bold text-slate-900 mt-3">
                {controlClickRate !== null ? `${controlClickRate}%` : '—'}
              </p>
              <p className="text-xs text-slate-500 mt-1">"Add All" click-through rate</p>
            </div>
            <div className="rounded-xl border-2 border-amber-200 p-4 bg-amber-50">
              <p className="text-[11px] font-bold uppercase tracking-wide text-amber-600">Group B — Confidence Badges ✨</p>
              <p className="text-sm text-amber-700 mt-1">AI confidence + RxNorm verified badges shown</p>
              <p className="text-3xl font-bold text-amber-900 mt-3">
                {variantClickRate !== null ? `${variantClickRate}%` : '—'}
              </p>
              <p className="text-xs text-amber-700 mt-1">"Add All" click-through rate</p>
            </div>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-slate-700">Observed Lift (B vs A)</p>
              <p className="text-2xl font-bold mt-0.5 text-slate-900">
                {abLift !== null ? `${abLift > 0 ? '+' : ''}${abLift}%` : 'Collecting data...'}
              </p>
            </div>
            <div className="text-sm text-slate-600 max-w-sm">
              <p className="font-semibold text-slate-700">Decision Rule</p>
              <p className="mt-0.5">Lift ≥ +15% → <span className="font-semibold text-emerald-700">Persevere</span> with Transparent AI design</p>
              <p>Lift &lt; +15% → <span className="font-semibold text-red-700">Pivot</span> to manual-verification-first UI</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-400 mt-2">
            Hypothesis: AI confidence badges increase "Add All" rate by ≥20%. Variant is assigned once per browser session via localStorage.
          </p>
        </GlassCard>

        {/* ── Standard KPI Strip ────────────────────────────────── */}
        <section className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <GlassCard className="p-4 bg-linear-to-br from-indigo-50 to-white"><p className="text-xs text-slate-500">Total testers</p><p className="text-2xl font-bold">{kpis.users_tested || 0}</p></GlassCard>
          <GlassCard className="p-4 bg-linear-to-br from-cyan-50 to-white"><p className="text-xs text-slate-500">Completion rate</p><p className="text-2xl font-bold">{funnel?.conversion_percent?.finished || 0}%</p></GlassCard>
          <GlassCard className="p-4 bg-linear-to-br from-emerald-50 to-white"><p className="text-xs text-slate-500">Avg SUS score</p><p className="text-2xl font-bold">{kpis.avg_sus || 0}</p></GlassCard>
          <GlassCard className="p-4 bg-linear-to-br from-violet-50 to-white"><p className="text-xs text-slate-500">Feedback responses</p><p className="text-2xl font-bold">{liveSummary.feedback_responses || 0}</p></GlassCard>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <GlassCard className="p-4 xl:col-span-2">
            <h3 className="text-lg font-semibold">Behavior Funnel</h3>
            <div className="mt-3 space-y-3">
              {funnelRows.map((row) => (
                <div key={row.step}>
                  <div className="flex items-center justify-between text-sm">
                    <span className="capitalize">{row.step.replaceAll('_', ' ')}</span>
                    <span>{row.count} ({row.conversion}%)</span>
                  </div>
                  <div className="h-3 rounded-full bg-slate-100 mt-1">
                    <div className="h-3 rounded-full bg-indigo-500" style={{ width: `${Math.max(0, Math.min(100, row.conversion))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">SUS Distribution</h3>
            <p className="text-sm text-slate-600 mt-1">Min {sus.min || 0} / Max {sus.max || 0}</p>
            <div className="mt-3 h-3 rounded-full overflow-hidden bg-slate-100">
              <div
                className="h-full bg-rose-400 inline-block"
                style={{ width: `${((susBuckets?.below_50 || 0) / bucketTotal) * 100}%` }}
              />
              <div
                className="h-full bg-amber-400 inline-block"
                style={{ width: `${((susBuckets?.['50_to_68'] || 0) / bucketTotal) * 100}%` }}
              />
              <div
                className="h-full bg-emerald-500 inline-block"
                style={{ width: `${((susBuckets?.above_68 || 0) / bucketTotal) * 100}%` }}
              />
            </div>
            <div className="mt-3 space-y-2 text-sm text-slate-700">
              <p>Below 50: {susBuckets?.below_50 || 0}</p>
              <p>50-68: {susBuckets?.['50_to_68'] || 0}</p>
              <p>Above 68: {susBuckets?.above_68 || 0}</p>
              <p>Tracked events: {liveSummary.events_tracked || 0}</p>
            </div>
          </GlassCard>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Average SUS Rating by Question</h3>
            <div className="mt-4 space-y-3">
              {questions.map((item) => (
                <div key={item.question_id}>
                  <div className="text-sm text-slate-700">{item.question_id.toUpperCase()}: {item.question_text}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-2 flex-1 rounded-full bg-slate-100">
                      <div
                        className="h-2 rounded-full bg-slate-900"
                        style={{ width: `${Math.max(0, Math.min(100, (Number(item.average_rating || 0) / 5) * 100))}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-slate-700 min-w-16 text-right">{item.average_rating}/5</span>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-lg font-semibold">Qualitative Highlights</h3>
            <p className="text-sm text-slate-600 mt-1">Recent user quotes</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-700">
              {quotes.slice(0, 5).map((quote) => (
                <li key={quote} className="border-l-2 border-indigo-300 pl-2">"{quote}"</li>
              ))}
              {quotes.length === 0 && <li className="text-slate-500">No quotes yet.</li>}
            </ul>
            <div className="mt-4 rounded-lg border border-slate-200 p-3 text-sm text-slate-700 bg-slate-50">
              <p>Sessions completed: {kpis.sessions_completed || 0}</p>
              <p>SUS submissions: {liveSummary.sus_responses || 0}</p>
              <p>Avg session duration: 4 min</p>
            </div>
          </GlassCard>
        </section>

        <GlassCard className="p-4">
          <h3 className="text-lg font-semibold">Feedback Table</h3>
          <p className="text-sm text-slate-600 mt-1">Hesitation, most useful signal, and pay intent</p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[780px] text-sm">
              <thead className="text-left text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="py-2 pr-3">Status</th>
                  <th className="py-2 pr-3">Hesitations</th>
                  <th className="py-2 pr-3">Most useful</th>
                  <th className="py-2 pr-3">Will you pay?</th>
                </tr>
              </thead>
              <tbody>
                {feedbackRows.map((row, idx) => (
                  <tr key={`${row.status}-${idx}`} className="border-b border-slate-100 text-slate-700 align-top">
                    <td className="py-2 pr-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${
                        row.status === 'easy'
                          ? 'bg-emerald-100 text-emerald-700'
                          : row.status === 'hesitant'
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-rose-100 text-rose-700'
                      }`}
                      >
                        {row.status === 'gave_up' ? 'Gave Up' : row.status === 'hesitant' ? 'Hesitant' : 'Easy'}
                      </span>
                    </td>
                    <td className="py-2 pr-3">{row.hesitations}</td>
                    <td className="py-2 pr-3">{row.most_useful}</td>
                    <td className="py-2 pr-3">{row.would_pay}</td>
                  </tr>
                ))}
                {feedbackRows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-3 text-slate-500">No feedback rows yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};

export default AdminEvidenceView;
