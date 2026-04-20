import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const Field = ({ label, hint, children, spanTwo = false }) => (
  <div className={`space-y-1 ${spanTwo ? 'sm:col-span-2' : ''}`}>
    <label className="block text-xs font-semibold text-slate-700">{label}</label>
    {children}
    {hint && <p className="text-xs text-slate-500">{hint}</p>}
  </div>
);

const ProfileView = ({
  GlassCard,
  profileError,
  profileForm,
  setProfileForm,
  profileSaving,
  profileActionLoading,
  submitProfile,
  profiles,
  activeProfileId,
  onAddNewProfile,
  onSwitchProfile,
  currentUser,
  onRequirePremium,
  caregiverPatientLimit,
  deleteAccountText,
  setDeleteAccountText,
  deleteAccountLoading,
  deleteMyAccount,
}) => {
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState('');
  const [addProfileOpen, setAddProfileOpen] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');
  const [newProfileEmail, setNewProfileEmail] = useState('');
  const [localInputError, setLocalInputError] = useState('');
  const [patientDraft, setPatientDraft] = useState({
    name: '',
    email: '',
  });

  const sanitizePersonNameInput = (value, maxLength = 120) => String(value || '')
    .replace(/[0-9]/g, '')
    .replace(/[^A-Za-z\s'-.]/g, '')
    .replace(/\s{2,}/g, ' ')
    .slice(0, maxLength);

  const sanitizeAgeInput = (value) => {
    const cleaned = String(value || '').replace(/[^0-9]/g, '').slice(0, 3);
    if (!cleaned) return '';
    const numeric = Number(cleaned);
    if (Number.isNaN(numeric)) return '';
    return String(Math.min(120, Math.max(0, numeric)));
  };

  const normalizeWhitespace = (value) => String(value || '').replace(/\s+/g, ' ').trim();
  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || '').trim());
  const isValidName = (name) => /^[A-Za-z][A-Za-z\s'-.]*$/.test(String(name || '').trim()) && !/\d/.test(String(name || ''));

  const canDelete = useMemo(() => {
    const email = String(currentUser && currentUser.email ? currentUser.email : '').trim().toLowerCase();
    return deleteAccountText.trim().toUpperCase() === 'DELETE'
      && confirmEmail.trim().toLowerCase() === email
      && Boolean(email);
  }, [confirmEmail, currentUser, deleteAccountText]);

  const isCaregiver = String(currentUser?.role || '').toLowerCase() === 'caregiver';
  const jumpToCaregiverSection = () => {
    document.getElementById('caregiver-patients')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const careTeamPatients = Array.isArray(profileForm.care_team_patients) ? profileForm.care_team_patients : [];
  const hasMultipleProfiles = Array.isArray(profiles) && profiles.length > 1;

  const addCareTeamPatient = () => {
    const name = normalizeWhitespace(patientDraft.name);
    const email = patientDraft.email.trim().toLowerCase();

    setLocalInputError('');
    if (!name && !email) return;
    if (!name || !isValidName(name)) {
      setLocalInputError('Caregiver patient name must contain letters only.');
      return;
    }
    if (email && !isValidEmail(email)) {
      setLocalInputError('Caregiver patient email must be valid.');
      return;
    }

    setProfileForm((previous) => {
      const nextPatients = Array.isArray(previous.care_team_patients) ? [...previous.care_team_patients] : [];
      const existingIndex = nextPatients.findIndex((patient) => String(patient.email || '').toLowerCase() === email);

      if (existingIndex < 0 && nextPatients.length >= caregiverPatientLimit) {
        if (onRequirePremium) onRequirePremium('caregiver_patient_limit');
        return previous;
      }

      const nextPatient = { name, email };
      if (existingIndex >= 0) {
        nextPatients[existingIndex] = nextPatient;
      } else {
        nextPatients.push(nextPatient);
      }
      return { ...previous, care_team_patients: nextPatients };
    });

    setPatientDraft({ name: '', email: '' });
  };

  const removeCareTeamPatient = (email) => {
    setProfileForm((previous) => ({
      ...previous,
      care_team_patients: (Array.isArray(previous.care_team_patients) ? previous.care_team_patients : []).filter(
        (patient) => String(patient.email || '').toLowerCase() !== String(email || '').toLowerCase(),
      ),
    }));
  };

  const confirmAddProfile = async () => {
    const normalizedName = normalizeWhitespace(newProfileName);
    const normalizedEmail = String(newProfileEmail || '').trim().toLowerCase();
    setLocalInputError('');
    if (!normalizedName || !isValidName(normalizedName)) {
      setLocalInputError('Profile name must contain letters only.');
      return;
    }
    if (normalizedEmail && !isValidEmail(normalizedEmail)) {
      setLocalInputError('Profile email is invalid.');
      return;
    }

    const success = await onAddNewProfile(newProfileName, newProfileEmail);
    if (success) {
      setAddProfileOpen(false);
      setNewProfileName('');
      setNewProfileEmail('');
    }
  };

  return (
    <motion.div key="profile" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-5 h-full overflow-y-auto pr-1">
      <GlassCard className="p-5 lg:p-6 bg-linear-to-r from-slate-50 via-white to-indigo-50 border-indigo-100">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-widest uppercase font-bold text-indigo-500">Account</p>
            <div className="flex items-center gap-3 mt-1">
              <h2 className="text-2xl lg:text-3xl font-bold text-slate-900">Profile</h2>
              {currentUser?.is_premium && (
                <span className="bg-indigo-100 text-indigo-800 text-xs font-semibold px-2.5 py-0.5 rounded-full inline-flex items-center gap-1 border border-indigo-200 shadow-sm mt-1">
                   ✨ Premium Active
                </span>
              )}
            </div>
            <p className="text-sm text-slate-600 mt-2">Keep each patient profile updated for accurate safety checks.</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                if (currentUser && !currentUser.is_premium) {
                  if (onRequirePremium) onRequirePremium('profile_limit');
                  return;
                }
                setAddProfileOpen(true);
              }}
              disabled={profileActionLoading}
              className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500 disabled:opacity-50"
            >
              {profileActionLoading ? 'Adding...' : 'Add New Profile'}
            </button>
            {isCaregiver && (
              <button onClick={jumpToCaregiverSection} className="px-4 py-2 rounded-lg border border-indigo-200 text-indigo-700 bg-white text-sm font-semibold hover:bg-indigo-50">
                Add Patient Profile
              </button>
            )}
          </div>
        </div>

        {hasMultipleProfiles && (
          <div className="mt-4">
            <label className="block text-xs font-semibold text-slate-700 mb-1">Active Profile</label>
            <select
              value={activeProfileId || ''}
              onChange={(e) => onSwitchProfile(e.target.value)}
              disabled={profileActionLoading}
              className="w-full max-w-xs bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              {(Array.isArray(profiles) ? profiles : []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name || 'Profile'}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">Switching profile updates medications, prescriptions, and safety analysis context.</p>
          </div>
        )}
      </GlassCard>

      <GlassCard>
        {profileError && <p className="mb-3 text-sm text-red-600">{profileError}</p>}
        {localInputError && <p className="mb-3 text-sm text-red-600">{localInputError}</p>}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Patient Name">
            <input value={profileForm.patient_name} onChange={(e) => setProfileForm((p) => ({ ...p, patient_name: sanitizePersonNameInput(e.target.value, 120) }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Patient full name" maxLength={120} />
          </Field>

          <Field label="Patient Email">
            <div>
              <input
                value={profileForm.patient_email}
                readOnly
                className="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-600 cursor-not-allowed"
                placeholder="patient@example.com"
              />
            </div>
          </Field>

          <Field label="Age">
            <input type="number" min="0" max="120" step="1" value={profileForm.age} onChange={(e) => setProfileForm((p) => ({ ...p, age: sanitizeAgeInput(e.target.value) }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 47" />
          </Field>

          <Field label="Chronic Conditions" spanTwo>
            <input value={profileForm.chronic_conditions_text} onChange={(e) => setProfileForm((p) => ({ ...p, chronic_conditions_text: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="List long-term conditions" />
          </Field>

          <Field label="Allergies" spanTwo>
            <input value={profileForm.allergies_text} onChange={(e) => setProfileForm((p) => ({ ...p, allergies_text: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="List known allergies" />
          </Field>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <input type="checkbox" checked={profileForm.kidney_disease} onChange={(e) => setProfileForm((p) => ({ ...p, kidney_disease: e.target.checked }))} className="mt-0.5" />
            <span className="text-sm text-slate-700">Kidney disease</span>
          </label>

          <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <input type="checkbox" checked={profileForm.liver_disease} onChange={(e) => setProfileForm((p) => ({ ...p, liver_disease: e.target.checked }))} className="mt-0.5" />
            <span className="text-sm text-slate-700">Liver disease</span>
          </label>
        </div>

        {isCaregiver && (
          <div id="caregiver-patients" className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Caregiver Patients</h3>
                <p className="text-sm text-slate-600 mt-1">Manage the people you support from one simple list.</p>
              </div>
              <button onClick={addCareTeamPatient} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500">
                Save Patient
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Patient Name">
                <input value={patientDraft.name} onChange={(e) => setPatientDraft((p) => ({ ...p, name: sanitizePersonNameInput(e.target.value, 120) }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Patient name" maxLength={120} />
              </Field>

              <Field label="Patient Email">
                <input value={patientDraft.email} onChange={(e) => setPatientDraft((p) => ({ ...p, email: String(e.target.value || '').slice(0, 120) }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="patient@example.com" maxLength={120} />
              </Field>
            </div>

            <div className="mt-4 space-y-2">
              {careTeamPatients.length === 0 ? (
                <p className="text-sm text-slate-500 italic">No patients added yet.</p>
              ) : (
                careTeamPatients.map((patient, index) => (
                  <div key={`${patient.email || patient.name || index}`} className="rounded-lg border border-slate-200 bg-white p-3 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{patient.name || 'Unnamed patient'}</p>
                      <p className="text-xs text-slate-500">{patient.email || 'No email'}</p>
                    </div>
                    <button onClick={() => removeCareTeamPatient(patient.email)} className="text-xs font-semibold text-red-600 hover:text-red-700">
                      Remove
                    </button>
                  </div>
                ))
              )}
              <p className="text-xs text-slate-500">Free tier allows {caregiverPatientLimit} patient profile. Upgrade to add more.</p>
            </div>
          </div>
        )}

        <div className="mt-4 flex items-start gap-2 rounded-lg border border-slate-200 px-3 py-2">
          <input id="privacy-consent-profile" type="checkbox" checked={profileForm.privacy_consent} onChange={(e) => setProfileForm((p) => ({ ...p, privacy_consent: e.target.checked }))} className="mt-0.5" />
          <label htmlFor="privacy-consent-profile" className="text-sm text-slate-700">I consent to secure processing of my health data for medication safety analysis.</label>
        </div>

        <div className="mt-4 flex justify-end">
          <button onClick={submitProfile} disabled={profileSaving} className="px-4 py-2 rounded-lg bg-indigo-600 text-white disabled:opacity-50">
            {profileSaving ? 'Saving...' : 'Save Profile'}
          </button>
        </div>
      </GlassCard>

      <GlassCard>
        <h3 className="text-lg font-semibold text-slate-900">Privacy</h3>
        <p className="text-sm text-slate-600 mt-1">Manage account deletion from here.</p>

        <div className="mt-4 space-y-3">
          {!deleteConfirmOpen ? (
            <button
              onClick={() => setDeleteConfirmOpen(true)}
              className="w-full px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700"
            >
              Start Account Deletion
            </button>
          ) : (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-700 font-semibold">Final confirmation required.</p>
              <p className="text-sm text-red-700 mt-1">Type DELETE and your account email to permanently remove your account and all stored data.</p>

              <input
                value={deleteAccountText}
                onChange={(e) => setDeleteAccountText(e.target.value)}
                className="mt-2 w-full bg-white border border-red-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Type DELETE"
              />

              <input
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                className="mt-2 w-full bg-white border border-red-200 rounded-lg px-3 py-2 text-sm"
                placeholder="Type your account email"
              />

              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => {
                    setDeleteConfirmOpen(false);
                    setDeleteAccountText('');
                    setConfirmEmail('');
                  }}
                  disabled={deleteAccountLoading}
                  className="flex-1 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel
                </button>

                <button
                  onClick={() => deleteMyAccount(confirmEmail)}
                  disabled={!canDelete || deleteAccountLoading}
                  className="flex-1 px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleteAccountLoading ? 'Deleting...' : 'Confirm Delete'}
                </button>
              </div>
            </div>
          )}
        </div>
      </GlassCard>

      <AnimatePresence>
        {addProfileOpen && (
          <div className="fixed inset-0 z-1200 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/45 backdrop-blur-sm"
              onClick={() => setAddProfileOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 12, scale: 0.98 }}
              className="relative w-full max-w-md rounded-2xl bg-white border border-slate-200 shadow-xl p-5"
            >
              <h3 className="text-lg font-semibold text-slate-900">Create New Patient Profile</h3>
              <p className="text-sm text-slate-600 mt-1">Confirm and enter patient details for the new profile.</p>

              <div className="mt-4 space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Patient Name</label>
                  <input
                    value={newProfileName}
                    onChange={(e) => setNewProfileName(sanitizePersonNameInput(e.target.value, 80))}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="Patient full name"
                    maxLength={80}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">Patient Email (optional)</label>
                  <input
                    value={newProfileEmail}
                    onChange={(e) => setNewProfileEmail(String(e.target.value || '').slice(0, 120))}
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                    placeholder="patient@example.com"
                    maxLength={120}
                  />
                </div>
              </div>

              <div className="mt-5 flex justify-end gap-2">
                <button
                  onClick={() => setAddProfileOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmAddProfile}
                  disabled={profileActionLoading || !newProfileName.trim()}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {profileActionLoading ? 'Creating...' : 'Confirm Add Profile'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default ProfileView;
