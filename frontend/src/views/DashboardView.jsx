import React from 'react';
import { motion } from 'framer-motion';
import { Activity, Pencil, Search, Shield, Trash2, Upload } from 'lucide-react';

const DashboardView = ({
  GlassCard,
  entranceVariants,
  meds,
  savedPrescriptions,
  interactions,
  profileRequired,
  onUploadPrescription,
  openSafetyPage,
  medSearch,
  setMedSearch,
  filteredMeds,
  getMedicationRiskTag,
  openSafetyForInteraction,
  renderHighlightedText,
  formatMedicationSource,
  openEditMed,
  deleteMed,
  manualError,
  manualDrugType,
  setManualDrugType,
  manualDrugName,
  setManualDrugName,
  handleManualAdd,
  manualDose,
  setManualDose,
  manualFrequency,
  setManualFrequency,
  manualSaving,
  uploadStage,
}) => {
  const highRiskCount = interactions.filter((inter) => inter.severity === 'High').length;

  return (
    <motion.div key="dashboard" initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 12 }} className="h-full min-h-0 flex flex-col gap-3 overflow-hidden">
      <motion.div custom={0.08} variants={entranceVariants} initial="hidden" animate="show" className="shrink-0 w-full max-w-5xl mx-auto">
        <GlassCard className="p-3 bg-linear-to-r from-indigo-50 via-white to-cyan-50">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold tracking-[0.15em] uppercase text-indigo-500">Care Control Center</p>
              <h2 className="text-xl lg:text-2xl font-bold text-slate-900 mt-1">Polypharmacy Safety Dashboard</h2>
              <p className="text-xs lg:text-sm text-slate-500 mt-1.5 max-w-2xl">Track prescriptions, OTC, and supplements with interaction and overdose screening.</p>
              {uploadStage !== 'idle' && (
                <p className="mt-2 inline-flex items-center rounded-full bg-indigo-50 border border-indigo-200 px-3 py-1 text-[11px] font-semibold text-indigo-700">
                  {uploadStage === 'uploading' && 'Uploading prescription...'}
                  {uploadStage === 'analyzing' && 'Analyzing prescription text...'}
                  {uploadStage === 'reviewing' && 'Prescription ready for review.'}
                  {uploadStage === 'completed' && 'Prescription processing complete.'}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2 lg:justify-end">
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 min-w-28 shadow-sm">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-slate-400" />
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Active</p>
                </div>
                <p className="text-lg font-bold text-slate-900 leading-none mt-1.5">{meds.length}</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 min-w-28 shadow-sm">
                <div className="flex items-center gap-2">
                  <Upload className="w-4 h-4 text-slate-400" />
                  <p className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Scans</p>
                </div>
                <p className="text-lg font-bold text-slate-900 leading-none mt-1.5">{savedPrescriptions.length}</p>
              </div>
              <button
                type="button"
                onClick={openSafetyPage}
                className={`rounded-xl border px-4 py-2.5 min-w-28 shadow-sm text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${highRiskCount > 0 ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-white'}`}
              >
                <div className="flex items-center gap-2">
                  <Shield className="w-4 h-4" style={{ color: highRiskCount > 0 ? '#ef4444' : '#10b981' }} />
                  <p className={`text-[10px] uppercase tracking-widest font-bold ${highRiskCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>High Risk</p>
                </div>
                <p className={`text-lg font-bold leading-none mt-1.5 ${highRiskCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{highRiskCount}</p>
              </button>
            </div>
          </div>
        </GlassCard>
      </motion.div>

      <motion.section custom={0.16} variants={entranceVariants} initial="hidden" animate="show" className="flex-1 min-h-0 w-full max-w-5xl mx-auto overflow-hidden">
        <GlassCard className="h-full flex flex-col min-h-0 overflow-hidden">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-3 pb-3 border-b border-slate-200 shrink-0">
            <div>
              <h3 className="text-base font-semibold text-slate-800">Active Medication Profile</h3>
              <p className="text-slate-500 text-xs mt-0.5">{meds.length} medication{meds.length !== 1 ? 's' : ''} tracked</p>
            </div>
            <button
              onClick={onUploadPrescription}
              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center justify-center gap-2 shadow-sm transition-all"
            >
              <Upload className="w-4 h-4" />
              Upload Prescription
            </button>
          </div>

          {profileRequired && (
            <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2 text-xs text-indigo-800">
              Complete your health profile to unlock medicine entry, prescription scans, and sharing.
            </div>
          )}

          <div className="relative mb-3 shrink-0">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input
              type="text"
              value={medSearch}
              onChange={(e) => setMedSearch(e.target.value)}
              placeholder="Search medications"
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-900 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>

          <div className="space-y-2 mb-4 min-h-24 flex-1 overflow-y-auto pr-2">
            {filteredMeds.length === 0 ? (
              <p className="text-gray-500 text-center py-6 italic text-sm">{medSearch.trim() ? 'No matches for this search.' : 'No medications tracked yet.'}</p>
            ) : (
              filteredMeds.map((med) => {
                const riskTag = getMedicationRiskTag(med.name);
                return (
                  <motion.div layout key={med.id} className="group flex items-start justify-between gap-3 p-2.5 border-l-4 border-l-indigo-500 bg-slate-50 rounded-md border-b border-slate-100 hover:bg-slate-50 transition-colors duration-150">
                    <div className="flex-1 min-w-0">
                      <p className="text-slate-800 text-sm font-semibold truncate">{renderHighlightedText(med.name, medSearch)}</p>
                      {(med.dose || med.frequency) && <p className="font-mono text-xs text-slate-500 mt-0.5 truncate">{med.dose || 'Dose N/A'} · {med.frequency || 'Frequency N/A'}</p>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {riskTag && (
                        <button
                          type="button"
                          onClick={() => openSafetyForInteraction(riskTag.interaction)}
                          className={`inline-flex items-center px-1.5 py-0.5 rounded-full border text-[10px] font-semibold ${riskTag.className} hover:brightness-95 focus:outline-none focus:ring-2 focus:ring-indigo-400`}
                          title="Open the matching safety report"
                        >
                          {riskTag.label}
                        </button>
                      )}
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">{formatMedicationSource(med.source)}</span>
                      <button onClick={() => openEditMed(med)} className="opacity-0 group-hover:opacity-100 p-1.5 text-indigo-500/80 hover:text-indigo-600 transition-all" title="Update medicine">
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button onClick={() => deleteMed(med.id)} className="opacity-0 group-hover:opacity-100 p-1.5 text-red-500/70 hover:text-red-500 transition-all">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>

          <div className="border-t border-slate-200 pt-3 space-y-2.5 shrink-0">
            {manualError && (
              <div className="p-2.5 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-sm text-red-700">{manualError}</p>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-600">Medication Type</label>
                <select
                  value={manualDrugType}
                  onChange={(e) => setManualDrugType(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option>Prescription medicine</option>
                  <option>Over-the-counter (OTC)</option>
                  <option>Supplement / Vitamin</option>
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-600">Medicine Name *</label>
                <input
                  type="text"
                  placeholder="e.g., Lisinopril"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  value={manualDrugName}
                  onChange={(e) => setManualDrugName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleManualAdd()}
                  maxLength={200}
                  autoComplete="off"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-600">Dose</label>
                <input
                  type="text"
                  placeholder="e.g., 500mg"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  value={manualDose}
                  onChange={(e) => setManualDose(e.target.value)}
                  maxLength={100}
                  autoComplete="off"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-600">How Often (Frequency)</label>
                <input
                  type="text"
                  placeholder="e.g., Twice daily"
                  list="frequency-options"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-slate-900 placeholder:text-slate-300 outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  value={manualFrequency}
                  onChange={(e) => setManualFrequency(e.target.value)}
                  maxLength={100}
                  autoComplete="off"
                />
                <datalist id="frequency-options">
                  <option value="Twice daily" />
                </datalist>
              </div>
            </div>
            <button
              onClick={handleManualAdd}
              disabled={manualSaving || !manualDrugName.trim()}
              className="w-full py-2 px-4 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {manualSaving ? 'Adding...' : 'Add Medication'}
            </button>
          </div>
        </GlassCard>
      </motion.section>
    </motion.div>
  );
};

export default DashboardView;
