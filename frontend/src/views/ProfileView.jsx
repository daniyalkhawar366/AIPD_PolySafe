import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';

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
  submitProfile,
  currentUser,
  deleteAccountText,
  setDeleteAccountText,
  deleteAccountLoading,
  deleteMyAccount,
}) => {
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState('');
  const [patientDraft, setPatientDraft] = useState({
    name: '',
    email: '',
    relationship: '',
    notes: '',
  });

  const canDelete = useMemo(() => {
    const email = String(currentUser && currentUser.email ? currentUser.email : '').trim().toLowerCase();
    return deleteAccountText.trim().toUpperCase() === 'DELETE'
      && confirmEmail.trim().toLowerCase() === email
      && Boolean(email);
  }, [confirmEmail, currentUser, deleteAccountText]);

  const isCaregiver = String(currentUser?.role || '').toLowerCase() === 'caregiver';

  const careTeamPatients = Array.isArray(profileForm.care_team_patients) ? profileForm.care_team_patients : [];

  const addCareTeamPatient = () => {
    const name = patientDraft.name.trim();
    const email = patientDraft.email.trim().toLowerCase();
    const relationship = patientDraft.relationship.trim();
    const notes = patientDraft.notes.trim();

    if (!name && !email) return;

    setProfileForm((previous) => {
      const nextPatients = Array.isArray(previous.care_team_patients) ? [...previous.care_team_patients] : [];
      const existingIndex = nextPatients.findIndex((patient) => String(patient.email || '').toLowerCase() === email);
      const nextPatient = { name, email, relationship, notes };
      if (existingIndex >= 0) {
        nextPatients[existingIndex] = nextPatient;
      } else {
        nextPatients.push(nextPatient);
      }
      return { ...previous, care_team_patients: nextPatients };
    });

    setPatientDraft({ name: '', email: '', relationship: '', notes: '' });
  };

  const removeCareTeamPatient = (email) => {
    setProfileForm((previous) => ({
      ...previous,
      care_team_patients: (Array.isArray(previous.care_team_patients) ? previous.care_team_patients : []).filter(
        (patient) => String(patient.email || '').toLowerCase() !== String(email || '').toLowerCase(),
      ),
    }));
  };

  return (
    <motion.div key="profile" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} className="space-y-5 h-full overflow-y-auto pr-1">
      <GlassCard className="p-5 lg:p-6 bg-linear-to-r from-slate-50 via-white to-indigo-50 border-indigo-100">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] tracking-widest uppercase font-bold text-indigo-500">Account</p>
            <h2 className="text-2xl lg:text-3xl font-bold text-slate-900 mt-1">Profile</h2>
            <p className="text-sm text-slate-600 mt-2">View and update your health details used for safer recommendations.</p>
            <p className="text-sm text-slate-800 mt-3 font-medium">Name: {currentUser && currentUser.name ? currentUser.name : 'User'}</p>
            <p className="text-xs text-slate-500">Email: {currentUser && currentUser.email ? currentUser.email : 'Not available'}</p>
          </div>
        </div>
      </GlassCard>

      <GlassCard>
        {profileError && <p className="mb-3 text-sm text-red-600">{profileError}</p>}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Age" hint="Used for age-related medication safety checks.">
            <input value={profileForm.age} onChange={(e) => setProfileForm((p) => ({ ...p, age: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 47" />
          </Field>

          <Field label="Gender Identity" hint="Shared with clinicians if needed for context.">
            <input value={profileForm.gender_identity} onChange={(e) => setProfileForm((p) => ({ ...p, gender_identity: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., Woman" />
          </Field>

          <Field label="Weight (kg)" hint="Helps with dose and risk interpretation.">
            <input value={profileForm.weight_kg} onChange={(e) => setProfileForm((p) => ({ ...p, weight_kg: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 72" />
          </Field>

          <Field label="Height (cm)" hint="Provides better health context for medication review.">
            <input value={profileForm.height_cm} onChange={(e) => setProfileForm((p) => ({ ...p, height_cm: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 168" />
          </Field>

          <Field label="Chronic Conditions" hint="Comma-separated. Example: diabetes, hypertension" spanTwo>
            <input value={profileForm.chronic_conditions_text} onChange={(e) => setProfileForm((p) => ({ ...p, chronic_conditions_text: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="List long-term conditions" />
          </Field>

          <Field label="Allergies" hint="Comma-separated. Example: penicillin, peanuts" spanTwo>
            <input value={profileForm.allergies_text} onChange={(e) => setProfileForm((p) => ({ ...p, allergies_text: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="List known allergies" />
          </Field>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <input type="checkbox" checked={profileForm.kidney_disease} onChange={(e) => setProfileForm((p) => ({ ...p, kidney_disease: e.target.checked }))} className="mt-0.5" />
            <span className="text-sm text-slate-700">I have kidney disease history.</span>
          </label>

          <label className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <input type="checkbox" checked={profileForm.liver_disease} onChange={(e) => setProfileForm((p) => ({ ...p, liver_disease: e.target.checked }))} className="mt-0.5" />
            <span className="text-sm text-slate-700">I have liver disease history.</span>
          </label>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Smoking Status" hint="Used for risk context and follow-up guidance.">
            <select
              value={profileForm.smoking_status}
              onChange={(e) => setProfileForm((p) => ({ ...p, smoking_status: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="unknown">Unknown</option>
              <option value="never">Never</option>
              <option value="former">Former</option>
              <option value="current">Current</option>
            </select>
          </Field>

          <Field label="Alcohol Use" hint="Used for alcohol-related medication warnings.">
            <select
              value={profileForm.alcohol_use}
              onChange={(e) => setProfileForm((p) => ({ ...p, alcohol_use: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="unknown">Unknown</option>
              <option value="none">None</option>
              <option value="social">Social</option>
              <option value="weekly">Weekly</option>
              <option value="daily">Daily</option>
            </select>
          </Field>

          <Field label="Grapefruit / Grapefruit Juice" hint="Triggers practical food-drug warnings for some medicines.">
            <select
              value={profileForm.grapefruit_use}
              onChange={(e) => setProfileForm((p) => ({ ...p, grapefruit_use: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="unknown">Unknown</option>
              <option value="none">None</option>
              <option value="sometimes">Sometimes</option>
              <option value="often">Often</option>
            </select>
          </Field>

          <Field label="Dairy / Calcium Timing" hint="Used for absorption warnings with certain medicines.">
            <select
              value={profileForm.dairy_use}
              onChange={(e) => setProfileForm((p) => ({ ...p, dairy_use: e.target.value }))}
              className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="unknown">Unknown</option>
              <option value="none">None</option>
              <option value="with_meds">Often taken with medicines</option>
              <option value="separate">Usually separated from medicines</option>
            </select>
          </Field>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          <Field label="eGFR" hint="Kidney marker used to adjust risk warnings.">
            <input value={profileForm.egfr} onChange={(e) => setProfileForm((p) => ({ ...p, egfr: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 72" />
          </Field>

          <Field label="ALT (U/L)" hint="Liver marker for safety context.">
            <input value={profileForm.alt_u_l} onChange={(e) => setProfileForm((p) => ({ ...p, alt_u_l: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 28" />
          </Field>

          <Field label="AST (U/L)" hint="Liver marker for safety context.">
            <input value={profileForm.ast_u_l} onChange={(e) => setProfileForm((p) => ({ ...p, ast_u_l: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 24" />
          </Field>

          <Field label="INR" hint="Bleeding-risk context if you use blood thinners.">
            <input value={profileForm.inr} onChange={(e) => setProfileForm((p) => ({ ...p, inr: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 2.4" />
          </Field>

          <Field label="Glucose (mg/dL)" hint="Used for diabetes control context.">
            <input value={profileForm.glucose_mg_dl} onChange={(e) => setProfileForm((p) => ({ ...p, glucose_mg_dl: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="e.g., 145" />
          </Field>
        </div>

        <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Emergency Contact Name" hint="Shown in exported summaries.">
            <input value={profileForm.emergency_contact_name} onChange={(e) => setProfileForm((p) => ({ ...p, emergency_contact_name: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Name" />
          </Field>

          <Field label="Emergency Contact Phone" hint="Shown in exported summaries.">
            <input value={profileForm.emergency_contact_phone} onChange={(e) => setProfileForm((p) => ({ ...p, emergency_contact_phone: e.target.value }))} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Phone number" />
          </Field>

          <Field label="Emergency Notes" hint="Any critical notes for the doctor or caregiver." spanTwo>
            <textarea value={profileForm.emergency_notes} onChange={(e) => setProfileForm((p) => ({ ...p, emergency_notes: e.target.value }))} className="w-full min-h-24 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Example: prefers morning calls; monitor BP after dose changes" />
          </Field>
        </div>

        {isCaregiver && (
          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">Caretaker Profile</h3>
                <p className="text-sm text-slate-600 mt-1">Keep a roster of the patients you support and their care notes in one place.</p>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Field label="Patient Name" hint="Add the patient you manage.">
                <input value={patientDraft.name} onChange={(e) => setPatientDraft((p) => ({ ...p, name: e.target.value }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Patient name" />
              </Field>

              <Field label="Patient Email" hint="Optional, but helps keep the roster organized.">
                <input value={patientDraft.email} onChange={(e) => setPatientDraft((p) => ({ ...p, email: e.target.value }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="patient@example.com" />
              </Field>

              <Field label="Relationship" hint="Example: spouse, parent, child, nurse." >
                <input value={patientDraft.relationship} onChange={(e) => setPatientDraft((p) => ({ ...p, relationship: e.target.value }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Relationship" />
              </Field>

              <Field label="Care Notes" hint="Anything useful for regular follow-up." >
                <input value={patientDraft.notes} onChange={(e) => setPatientDraft((p) => ({ ...p, notes: e.target.value }))} className="w-full bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm" placeholder="Notes" />
              </Field>
            </div>

            <div className="mt-3 flex justify-end">
              <button onClick={addCareTeamPatient} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-500">
                Add Patient
              </button>
            </div>

            <div className="mt-4 space-y-2">
              {careTeamPatients.length === 0 ? (
                <p className="text-sm text-slate-500 italic">No patients added yet.</p>
              ) : (
                careTeamPatients.map((patient, index) => (
                  <div key={`${patient.email || patient.name || index}`} className="rounded-lg border border-slate-200 bg-white p-3 flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{patient.name || 'Unnamed patient'}</p>
                      <p className="text-xs text-slate-500">{patient.email || 'No email'}{patient.relationship ? ` • ${patient.relationship}` : ''}</p>
                      {patient.notes && <p className="text-xs text-slate-600 mt-1">{patient.notes}</p>}
                    </div>
                    <button onClick={() => removeCareTeamPatient(patient.email)} className="text-xs font-semibold text-red-600 hover:text-red-700">
                      Remove
                    </button>
                  </div>
                ))
              )}
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
    </motion.div>
  );
};

export default ProfileView;
