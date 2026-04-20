import React from 'react';
import { CheckCircle, Plus, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const AppModals = ({
  filePreviewOpen,
  filePreviewUrl,
  filePreviewName,
  filePreviewMime,
  setFilePreviewUrl,
  setFilePreviewOpen,
  prescriptionModalOpen,
  setPrescriptionModalOpen,
  manualError,
  isDragOver,
  setIsDragOver,
  handleDropUpload,
  handleUpload,
  isUploading,
  ocrResults,
  closeOcrReviewModal,
  ocrActionInfo,
  ocrReviewItems,
  updateReviewedDrug,
  confirmDrug,
  confirmAllReviewedDrugs,
  bulkAddLoading,
  savePrescriptionRecord,
  recordSaving,
  rawText,
  ocrRecordSaved,
  pendingEditMed,
  updateMedLoading,
  setPendingEditMed,
  editMedName,
  setEditMedName,
  editMedType,
  setEditMedType,
  editMedDose,
  setEditMedDose,
  editMedFrequency,
  setEditMedFrequency,
  submitEditMed,
  pendingDeleteRecordId,
  deleteRecordLoading,
  setPendingDeleteRecordId,
  deletePrescriptionRecord,
  pendingDeleteMedId,
  deleteMedLoading,
  setPendingDeleteMedId,
  confirmDeleteMed,
  premiumModalOpen,
  setPremiumModalOpen,
  premiumContext,
  premiumPriceUsd,
  onOpenPaymentPage,
}) => {
  const premiumMessages = {
    medicine_limit: {
      title: 'Medicine limit reached',
      body: 'Free tier supports up to 6 medicines. Upgrade to Premium to track more medications safely.',
    },
    prescription_limit: {
      title: 'Prescription archive limit reached',
      body: 'Free tier supports up to 2 saved prescriptions. Upgrade to Premium for an expanded prescription history.',
    },
    caregiver_patient_limit: {
      title: 'Caregiver roster limit reached',
      body: 'Free caregiver plan supports 1 patient profile. Upgrade to Premium to manage multiple patients.',
    },
    profile_limit: {
      title: 'Profile limit reached',
      body: 'Free tier supports one profile per account. Upgrade to Premium to add and manage multiple profiles.',
    },
    general: {
      title: 'Premium feature',
      body: 'Upgrade to Premium to unlock advanced patient safety tools.',
    },
  };

  const premiumCopy = premiumMessages[premiumContext] || premiumMessages.general;

  const closeFilePreview = () => {
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFilePreviewUrl('');
    setFilePreviewOpen(false);
  };

  return (
    <AnimatePresence>
      {filePreviewOpen && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-998">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={closeFilePreview}
            className="absolute inset-0 bg-black/55 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.98 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="relative w-full max-w-6xl h-[86vh] bg-white rounded-2xl shadow-xl ring-1 ring-slate-900/10 overflow-hidden"
          >
            <div className="h-12 px-4 border-b border-slate-200 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-900 truncate pr-4">{filePreviewName}</p>
              <button onClick={closeFilePreview} className="text-sm text-slate-500 hover:text-slate-800">
                Close
              </button>
            </div>
            {filePreviewUrl && String(filePreviewMime || '').startsWith('image/') ? (
              <div className="w-full h-[calc(86vh-48px)] bg-slate-50 flex items-center justify-center overflow-auto p-4">
                <img src={filePreviewUrl} alt="Uploaded prescription preview" className="max-w-full max-h-full object-contain rounded-lg shadow-sm" />
              </div>
            ) : (
              <iframe src={filePreviewUrl} title="Uploaded prescription preview" className="w-full h-[calc(86vh-48px)] bg-slate-50" />
            )}
          </motion.div>
        </div>
      )}

      {prescriptionModalOpen && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-50">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setPrescriptionModalOpen(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.2 }}
            className="relative bg-white border border-slate-200 rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
          >
            <div className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900">Upload Prescription</h2>
                <p className="text-sm text-slate-500 mt-0.5">Upload and verify extracted medications</p>
              </div>
              <button
                onClick={() => setPrescriptionModalOpen(false)}
                className="p-2 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-slate-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {manualError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
                  <p className="text-sm text-red-700">{manualError}</p>
                </div>
              )}

              <label
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragEnter={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleDropUpload}
                className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${isDragOver ? 'border-indigo-400 bg-indigo-50/60 scale-[1.01]' : 'border-indigo-200 hover:border-indigo-300 hover:bg-indigo-50/40'}`}
              >
                <input type="file" className="hidden" onChange={handleUpload} accept="image/*,.pdf" />
                {isUploading ? (
                  <div className="space-y-3">
                    <motion.div animate={{ rotate: 360 }} transition={{ duration: 0.9, repeat: Infinity }} className="w-10 h-10 border-2 border-indigo-600 border-t-transparent rounded-full mx-auto" />
                    <p className="text-sm font-semibold text-indigo-700">Analyzing prescription...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <motion.div animate={{ scale: 1 }} transition={{ duration: 0.2 }}>
                      <Plus className="w-12 h-12 text-indigo-500 mx-auto" />
                    </motion.div>
                    <div>
                      <p className="text-base font-semibold text-slate-900">Drop file or click to upload</p>
                      <p className="text-sm text-slate-500 mt-1">PNG, JPG, or PDF (max 10MB)</p>
                    </div>
                  </div>
                )}
              </label>
            </div>
          </motion.div>
        </div>
      )}

      {ocrResults && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-999">
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={closeOcrReviewModal} className="absolute inset-0 bg-black/70 backdrop-blur-md" />

          <motion.div initial={{ opacity: 0, scale: 0.9, y: 20 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.9, y: 20 }} className="relative bg-white border border-slate-200 rounded-4xl shadow-xl p-8 w-full max-w-lg overflow-hidden">
            <div className="absolute inset-0 bg-linear-to-br from-indigo-500/10 to-transparent pointer-events-none" />

            <div className="flex justify-between items-center mb-8 relative z-10">
              <div>
                <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Verify Results</h2>
                <p className="text-slate-500 text-sm mt-1">Review extracted medicines, then Save record and/or Add medicines to profile.</p>
              </div>
              <button onClick={closeOcrReviewModal} className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-slate-700 hover:bg-slate-100 rounded-full transition-all">
                <span className="text-2xl">&times;</span>
              </button>
            </div>

            {ocrActionInfo && (
              <div className="mb-4 p-3 rounded-xl border border-emerald-200 bg-emerald-50 relative z-10">
                <p className="text-sm text-emerald-800">{ocrActionInfo}</p>
              </div>
            )}

            <div className="max-h-80 overflow-y-auto space-y-3 pr-2 relative z-10">
              {ocrReviewItems.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-gray-500 italic">All detected medications were added or no results remain to review.</p>
                </div>
              ) : (
                ocrReviewItems.map((drug, index) => (
                  <div key={drug.name} className="group p-4 bg-white/5 rounded-2xl border border-white/5 hover:border-indigo-500/30 transition-all space-y-3">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center">
                        <CheckCircle className="w-6 h-6 text-indigo-400" />
                      </div>
                      <div className="flex-1">
                        <p className="text-slate-900 font-bold text-lg">{drug.name}</p>
                        <p className="text-gray-500 text-xs uppercase tracking-tighter">{drug.valid ? 'Verified with RxNorm' : 'Unmatched name: review and confirm'}</p>
                        {drug.duplicate_in_profile && (
                          <p className="mt-1 text-[11px] font-semibold text-amber-700 bg-amber-50 border border-amber-200 inline-flex px-2 py-0.5 rounded-full">
                            Already in profile - will be skipped
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-center">
                      <div className="space-y-2">
                        <input
                          type="text"
                          className="w-full bg-white/80 border border-slate-200 rounded-xl px-4 py-3 text-slate-900 outline-none"
                          value={drug.draftName}
                          onChange={(e) => updateReviewedDrug(index, 'draftName', e.target.value)}
                          placeholder="Edit medicine name before saving"
                          maxLength={200}
                        />
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          <input
                            type="text"
                            className="w-full bg-white/80 border border-slate-200 rounded-xl px-4 py-2 text-slate-900 outline-none"
                            value={drug.draftDose || ''}
                            onChange={(e) => updateReviewedDrug(index, 'draftDose', e.target.value)}
                            placeholder="Dose (e.g., 500mg)"
                            maxLength={100}
                          />
                          <input
                            type="text"
                            className="w-full bg-white/80 border border-slate-200 rounded-xl px-4 py-2 text-slate-900 outline-none"
                            value={drug.draftFrequency || ''}
                            onChange={(e) => updateReviewedDrug(index, 'draftFrequency', e.target.value)}
                            placeholder="Frequency (e.g., BID)"
                            maxLength={100}
                          />
                        </div>
                      </div>
                      <button
                        onClick={() => confirmDrug(drug)}
                        disabled={drug.duplicate_in_profile || drug.action === 'skip'}
                        className="bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-3 rounded-xl font-bold transition-all inline-flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <Plus className="w-5 h-5" /> {drug.duplicate_in_profile || drug.action === 'skip' ? 'Skipped' : 'Add'}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>

            <div className="mt-8 relative z-10 border-t border-white/5 pt-6 space-y-3">
              <button
                onClick={confirmAllReviewedDrugs}
                disabled={ocrReviewItems.length === 0 || bulkAddLoading}
                className="w-full py-4 bg-slate-100 hover:bg-slate-200 text-slate-900 rounded-2xl font-bold transition-all disabled:opacity-60"
              >
                {bulkAddLoading ? 'Adding medicines...' : 'Add All Medicines to Profile'}
              </button>
              <button
                onClick={savePrescriptionRecord}
                disabled={recordSaving || !rawText.trim() || ocrRecordSaved}
                className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-2xl font-bold transition-all disabled:opacity-60"
              >
                {recordSaving ? 'Saving...' : ocrRecordSaved ? 'Prescription Saved' : 'Save Prescription Record'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {pendingEditMed && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-1000">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !updateMedLoading && setPendingEditMed(null)}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            className="relative w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-xl p-5"
          >
            <h3 className="text-lg font-semibold text-slate-900">Update Medicine</h3>
            <div className="mt-3 space-y-2">
              <input value={editMedName} onChange={(e) => setEditMedName(e.target.value)} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Medicine name" maxLength={200} />
              <select value={editMedType} onChange={(e) => setEditMedType(e.target.value)} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm">
                <option>Prescription medicine</option>
                <option>Over-the-counter (OTC)</option>
                <option>Supplement / Vitamin</option>
              </select>
              <input value={editMedDose} onChange={(e) => setEditMedDose(e.target.value)} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Dose" maxLength={100} />
              <input value={editMedFrequency} onChange={(e) => setEditMedFrequency(e.target.value)} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Frequency" maxLength={100} />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setPendingEditMed(null)} disabled={updateMedLoading} className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700">Cancel</button>
              <button onClick={submitEditMed} disabled={updateMedLoading} className="px-4 py-2 rounded-lg bg-indigo-600 text-white disabled:opacity-50">
                {updateMedLoading ? 'Updating...' : 'Update'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {pendingDeleteRecordId && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-1000">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !deleteRecordLoading && setPendingDeleteRecordId(null)}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.16 }}
            className="relative w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl p-5"
          >
            <h3 className="text-lg font-semibold text-slate-900">Delete Prescription Record?</h3>
            <p className="text-sm text-slate-600 mt-2">This removes only the saved prescription file and OCR text from history.</p>
            <p className="text-sm text-slate-600 mt-1">Your medications already added to the profile will stay unchanged.</p>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setPendingDeleteRecordId(null)}
                disabled={deleteRecordLoading}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => deletePrescriptionRecord(pendingDeleteRecordId)}
                disabled={deleteRecordLoading}
                className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteRecordLoading ? 'Deleting...' : 'Delete Record'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {pendingDeleteMedId && (
        <div className="fixed inset-0 flex items-center justify-center p-4 z-1000">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => !deleteMedLoading && setPendingDeleteMedId(null)}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.16 }}
            className="relative w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl p-5"
          >
            <h3 className="text-lg font-semibold text-slate-900">Delete Medicine?</h3>
            <p className="text-sm text-slate-600 mt-2">This removes the medicine from your active profile and updates your safety report.</p>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setPendingDeleteMedId(null)}
                disabled={deleteMedLoading}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => confirmDeleteMed(pendingDeleteMedId)}
                disabled={deleteMedLoading}
                className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMedLoading ? 'Deleting...' : 'Delete Medicine'}
              </button>
            </div>
          </motion.div>
        </div>
      )}

      {premiumModalOpen && (
        <div className="fixed inset-0 z-1100 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setPremiumModalOpen(false)}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            className="relative w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl p-6"
          >
            <p className="text-[11px] tracking-widest uppercase font-bold text-indigo-500">Premium</p>
            <h3 className="text-xl font-bold text-slate-900 mt-1">{premiumCopy.title}</h3>
            <p className="text-sm text-slate-600 mt-2">{premiumCopy.body}</p>

            <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50 p-4">
              <p className="text-xs text-indigo-700 uppercase font-semibold tracking-wide">Premium Plan</p>
              <p className="text-2xl font-bold text-indigo-700 mt-1">${premiumPriceUsd}/month</p>
              <p className="text-xs text-indigo-700 mt-1">Includes multi-patient caregiver profiles and higher safety tracking limits.</p>
            </div>

            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                onClick={() => setPremiumModalOpen(false)}
                className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Not now
              </button>
              <button
                onClick={() => {
                  setPremiumModalOpen(false);
                  if (onOpenPaymentPage) onOpenPaymentPage();
                }}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500"
              >
                Upgrade Now
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default AppModals;
