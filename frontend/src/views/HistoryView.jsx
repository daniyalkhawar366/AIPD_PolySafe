import React from 'react';
import { motion } from 'framer-motion';

const HistoryView = ({
  GlassCard,
  savedPrescriptions,
  formatPrescriptionDate,
  openPrescriptionFile,
  filePreviewLoading,
  setPendingDeleteRecordId,
  setPrescriptionModalOpen,
}) => (
  <motion.div key="history" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-5">
    <GlassCard className="p-5 lg:p-6 bg-linear-to-r from-slate-50 via-white to-indigo-50 border-indigo-100">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-[11px] tracking-widest uppercase font-bold text-indigo-500">Record Archive</p>
          <h2 className="text-2xl lg:text-3xl font-bold text-slate-900 mt-1">Prescriptions</h2>
          <p className="text-sm text-slate-600 mt-2">Review prior uploads, inspect extracted text, and reopen the original uploaded file.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-slate-200 bg-white p-3 min-w-40">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold">Saved Records</p>
            <p className="text-xl font-bold text-slate-900 mt-1">{savedPrescriptions.length}</p>
          </div>
          <button
            onClick={() => setPrescriptionModalOpen(true)}
            className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-2 rounded-lg font-semibold transition-all"
          >
            Upload Prescription
          </button>
        </div>
      </div>
    </GlassCard>

    <GlassCard>
      <div className="space-y-3 max-h-128 overflow-y-auto pr-2">
        {savedPrescriptions.length === 0 ? (
          <p className="text-gray-500 italic text-sm">No records saved yet. Upload and save a prescription to build your archive.</p>
        ) : (
          savedPrescriptions.map((record) => (
            <div key={record.id} className="p-4 bg-slate-50 rounded-xl border border-slate-200">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-3">
                <div>
                  <p className="text-indigo-500 text-[10px] uppercase mb-1 font-bold tracking-widest">Saved Prescription</p>
                  {formatPrescriptionDate(record.date) && <p className="text-xs text-slate-500">{formatPrescriptionDate(record.date)}</p>}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openPrescriptionFile(record.id)}
                    disabled={!record.has_file || filePreviewLoading}
                    className="text-xs bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-200 disabled:text-slate-400 text-white px-3 py-2 rounded-lg font-semibold transition-all"
                  >
                    {filePreviewLoading ? 'Opening...' : 'View Uploaded File'}
                  </button>
                  <button
                    onClick={() => setPendingDeleteRecordId(record.id)}
                    className="text-xs text-red-500 hover:text-red-700 font-semibold"
                  >
                    Delete
                  </button>
                </div>
              </div>
              <p className="text-slate-700 text-sm font-mono wrap-break-word whitespace-pre-wrap">{record.raw_text}</p>
            </div>
          ))
        )}
      </div>
    </GlassCard>
  </motion.div>
);

export default HistoryView;
