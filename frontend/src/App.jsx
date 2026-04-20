import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  Shield,
  Upload,
  Trash2,
  Eye,
  EyeOff,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import SafetyAnalysisView from './SafetyAnalysisDesignReference';
import AppSidebar from './components/AppSidebar';
import AppModals from './components/AppModals';
import DashboardView from './views/DashboardView';
import HistoryView from './views/HistoryView';
import ProfileView from './views/ProfileView';
import UpgradeView from './views/UpgradeView';

const appLogo = '/favicon.svg';

const GlassCard = ({ children, className = '' }) => (
  <div className={`bg-white rounded-lg shadow-sm ring-1 ring-slate-900/5 p-4 ${className}`}>
    {children}
  </div>
);

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';
const TOKEN_KEY = 'polysafe_token';
const SAVED_ACCOUNTS_KEY = 'polysafe_saved_accounts';
const COOKIE_SESSION_TOKEN = '__cookie_session__';
const CACHE_MEDS_KEY = 'polysafe_cache_meds';
const CACHE_PRESCRIPTIONS_KEY = 'polysafe_cache_prescriptions';
const CACHE_SAFETY_KEY = 'polysafe_cache_safety';
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || import.meta.env.REACT_APP_GOOGLE_CLIENT_ID || '';
axios.defaults.headers.common['ngrok-skip-browser-warning'] = '69420';
axios.defaults.withCredentials = true;
let authInterceptorInstalled = false;
let authResponseInterceptorInstalled = false;

const setAuthHeader = (token) => {
  if (token && token !== COOKIE_SESSION_TOKEN) {
    axios.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete axios.defaults.headers.common.Authorization;
  }
};

const getAuthConfig = (token) => {
  const authToken = token || localStorage.getItem(TOKEN_KEY) || '';
  if (!authToken || authToken === COOKIE_SESSION_TOKEN) {
    return { withCredentials: true };
  }
  return { withCredentials: true, headers: { Authorization: `Bearer ${authToken}` } };
};

const formatUserName = (fullName) => {
  if (!fullName) return '';
  const nameParts = fullName.trim().split(/\s+/);
  if (nameParts.length === 1) return nameParts[0];
  if (nameParts.length === 2) return fullName;
  // For 3+ names, return middle name or last name if only 3 names
  if (nameParts.length === 3) return nameParts[1];
  // For more than 3 names, return last 2
  return `${nameParts[nameParts.length - 2]} ${nameParts[nameParts.length - 1]}`;
};

const MANUAL_SOURCE_DEFAULT = 'Prescription medicine';
const PREMIUM_PRICE_USD = 5;
const FREE_TIER_MED_LIMIT = 6;
const FREE_TIER_PRESCRIPTION_LIMIT = 2;
const FREE_TIER_CAREGIVER_PATIENT_LIMIT = 1;
const FREE_TIER_PROFILE_LIMIT = 1;
const DUPLICATE_MEDICATION_ALIASES = {
  acetaminophen: ['acetaminophen', 'paracetamol', 'apap'],
  ibuprofen: ['ibuprofen'],
  aspirin: ['aspirin', 'asa'],
  naproxen: ['naproxen'],
  diclofenac: ['diclofenac'],
  metformin: ['metformin'],
  amlodipine: ['amlodipine'],
  atorvastatin: ['atorvastatin'],
  lisinopril: ['lisinopril'],
  losartan: ['losartan'],
  simvastatin: ['simvastatin'],
};
const VIEW_TO_PATH = {
  dashboard: '/dashboard',
  safety: '/safety',
  history: '/history',
  profile: '/profile',
  upgrade: '/upgrade',
};

const PATH_TO_VIEW = {
  '/dashboard': 'dashboard',
  '/safety': 'safety',
  '/history': 'history',
  '/profile': 'profile',
  '/upgrade': 'upgrade',
  '/': 'dashboard',
};

const getViewFromPath = (pathName = '/') => PATH_TO_VIEW[pathName] || 'dashboard';

const App = () => {
  const [authMode, setAuthMode] = useState('login');
  const [authName, setAuthName] = useState('');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authRole, setAuthRole] = useState('patient');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetCode, setResetCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmNewPassword, setConfirmNewPassword] = useState('');
  const [forgotOtpSent, setForgotOtpSent] = useState(false);
  const [forgotOtpVerified, setForgotOtpVerified] = useState(false);
  const [showAuthPassword, setShowAuthPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authInfo, setAuthInfo] = useState('');
  const [minPasswordLength, setMinPasswordLength] = useState(8);
  const [googleEnabled, setGoogleEnabled] = useState(Boolean(GOOGLE_CLIENT_ID));
  const [googleButtonReady, setGoogleButtonReady] = useState(false);
  const [googleUiError, setGoogleUiError] = useState('');
  const [googleAuthLoading, setGoogleAuthLoading] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const googleSlotRef = useRef(null);
  const googleRenderedRef = useRef(false);
  const manualLogoutRef = useRef(false);
  const hasShownProfileNudgeRef = useRef(false);

  const [token, setToken] = useState(localStorage.getItem(TOKEN_KEY) || '');
  const [currentUser, setCurrentUser] = useState(null);
  const [authHydrated, setAuthHydrated] = useState(false);

  const [meds, setMeds] = useState([]);
  const [interactions, setInteractions] = useState([]);
  const [safetyReport, setSafetyReport] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStage, setUploadStage] = useState('idle');
  const [ocrResults, setOcrResults] = useState(null);
  const [ocrReviewItems, setOcrReviewItems] = useState([]);
  const [rawText, setRawText] = useState('');
  const [uploadedFileName, setUploadedFileName] = useState('');
  const [ocrConfidence, setOcrConfidence] = useState(0);
  const [savedPrescriptions, setSavedPrescriptions] = useState([]);
  const [manualDrugName, setManualDrugName] = useState('');
  const [manualDrugType, setManualDrugType] = useState(MANUAL_SOURCE_DEFAULT);
  const [manualDose, setManualDose] = useState('');
  const [manualFrequency, setManualFrequency] = useState('');
  const [manualError, setManualError] = useState('');
  const [medSearch, setMedSearch] = useState('');
  const [manualSaving, setManualSaving] = useState(false);
  const [recordSaving, setRecordSaving] = useState(false);
  const [loading, setLoading] = useState(false);

  const [activeView, setActiveView] = useState(getViewFromPath(window.location.pathname));
  const [offlineMode, setOfflineMode] = useState(false);
  const [offlineInfo, setOfflineInfo] = useState('');
  const [profileNudgeVisible, setProfileNudgeVisible] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileActionLoading, setProfileActionLoading] = useState(false);
  const [profileSwitching, setProfileSwitching] = useState(false);
  const [profileError, setProfileError] = useState('');
  const [profileForm, setProfileForm] = useState({
    patient_name: '',
    patient_email: '',
    age: '',
    gender_identity: '',
    weight_kg: '',
    height_cm: '',
    chronic_conditions_text: '',
    allergies_text: '',
    kidney_disease: false,
    liver_disease: false,
    smoking_status: 'unknown',
    alcohol_use: 'unknown',
    grapefruit_use: 'unknown',
    dairy_use: 'unknown',
    egfr: '',
    alt_u_l: '',
    ast_u_l: '',
    inr: '',
    glucose_mg_dl: '',
    emergency_contact_name: '',
    emergency_contact_phone: '',
    emergency_notes: '',
    care_team_patients: [],
    privacy_consent: false,
  });

  const [deleteAccountText, setDeleteAccountText] = useState('');
  const [deleteAccountLoading, setDeleteAccountLoading] = useState(false);
  const [updateMedLoading, setUpdateMedLoading] = useState(false);
  const [pendingEditMed, setPendingEditMed] = useState(null);
  const [editMedName, setEditMedName] = useState('');
  const [editMedType, setEditMedType] = useState(MANUAL_SOURCE_DEFAULT);
  const [editMedDose, setEditMedDose] = useState('');
  const [editMedFrequency, setEditMedFrequency] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const [filePreviewOpen, setFilePreviewOpen] = useState(false);
  const [filePreviewLoading, setFilePreviewLoading] = useState(false);
  const [filePreviewUrl, setFilePreviewUrl] = useState('');
  const [filePreviewName, setFilePreviewName] = useState('');
  const [filePreviewMime, setFilePreviewMime] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [prescriptionModalOpen, setPrescriptionModalOpen] = useState(false);
  const [sessionRestorePending, setSessionRestorePending] = useState(false);
  const [pendingDeleteRecordId, setPendingDeleteRecordId] = useState(null);
  const [pendingDeleteMedId, setPendingDeleteMedId] = useState(null);
  const [deleteRecordLoading, setDeleteRecordLoading] = useState(false);
  const [deleteMedLoading, setDeleteMedLoading] = useState(false);
  const [ocrRecordSaved, setOcrRecordSaved] = useState(false);
  const [bulkAddLoading, setBulkAddLoading] = useState(false);
  const [ocrActionInfo, setOcrActionInfo] = useState('');
  const [ocrMedsAdded, setOcrMedsAdded] = useState(false);
  const [selectedSafetyInteraction, setSelectedSafetyInteraction] = useState(null);
  const [premiumModalOpen, setPremiumModalOpen] = useState(false);
  const [congratsModalOpen, setCongratsModalOpen] = useState(false);
  const [premiumContext, setPremiumContext] = useState('general');
  const [logoutConfirmOpen, setLogoutConfirmOpen] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const [savedAccounts, setSavedAccounts] = useState(() => {
    try {
      const raw = localStorage.getItem(SAVED_ACCOUNTS_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });
  const [accountSwitcherOpen, setAccountSwitcherOpen] = useState(false);
  const [switchingAccountEmail, setSwitchingAccountEmail] = useState('');
  const safetyRefreshTimerRef = useRef(null);

  const entranceVariants = {
    hidden: { opacity: 0, y: 14 },
    show: (delay = 0) => ({
      opacity: 1,
      y: 0,
      transition: { duration: 0.28, ease: 'easeOut', delay },
    }),
  };

  const loadCache = (key, fallback = null) => {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  };

  const saveCache = (key, value) => {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // no-op: storage can fail in private mode or quota limits
    }
  };

  const parseCsvList = (rawText) => String(rawText || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

  const normalizeWhitespace = (value) => String(value || '').replace(/\s+/g, ' ').trim();

  const sanitizePersonNameInput = (value, maxLength = 120) => String(value || '')
    .replace(/[0-9]/g, '')
    .replace(/[^A-Za-z\s'-.]/g, '')
    .replace(/\s{2,}/g, ' ')
    .slice(0, maxLength);

  const sanitizeMedicationNameInput = (value, maxLength = 200) => String(value || '')
    .replace(/[0-9]/g, '')
    .replace(/[^A-Za-z\s'().-]/g, '')
    .replace(/\s{2,}/g, ' ')
    .slice(0, maxLength);

  const sanitizeDoseInput = (value, maxLength = 100) => String(value || '')
    .replace(/[^A-Za-z0-9\s.,/%()-]/g, '')
    .replace(/\s{2,}/g, ' ')
    .slice(0, maxLength);

  const sanitizeFrequencyInput = (value, maxLength = 100) => String(value || '')
    .replace(/[^A-Za-z0-9\s.,/()-]/g, '')
    .replace(/\s{2,}/g, ' ')
    .slice(0, maxLength);

  const sanitizeNumericInput = (value, { maxLength = 8, allowDecimal = false } = {}) => {
    const raw = String(value || '').trim();
    const negativeStripped = raw.replace(/-/g, '');
    const cleaned = allowDecimal
      ? negativeStripped.replace(/[^0-9.]/g, '')
      : negativeStripped.replace(/\D/g, '');
    const [whole, ...rest] = cleaned.split('.');
    const normalized = allowDecimal && rest.length > 0 ? `${whole}.${rest.join('')}` : whole;
    return normalized.slice(0, maxLength);
  };

  const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || '').trim());

  const isValidPersonName = (name, { required = false, maxLength = 120 } = {}) => {
    const normalized = normalizeWhitespace(name);
    if (!normalized) return !required;
    if (normalized.length > maxLength) return false;
    if (/\d/.test(normalized)) return false;
    return /^[A-Za-z][A-Za-z\s'-.]*$/.test(normalized);
  };

  const parseNumberField = (value) => {
    const normalized = String(value ?? '').trim();
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
  };

  const normalizeMedicationDuplicateKey = (name) => {
    const lowered = String(name || '').trim().toLowerCase();
    if (!lowered) return '';
    for (const [canonical, aliases] of Object.entries(DUPLICATE_MEDICATION_ALIASES)) {
      if (aliases.some((alias) => lowered.includes(alias))) return canonical;
    }
    return lowered;
  };

  const persistSavedAccounts = (nextAccounts) => {
    const sanitized = Array.isArray(nextAccounts)
      ? nextAccounts.filter((item) => item?.email && item?.token)
      : [];
    setSavedAccounts(sanitized);
    saveCache(SAVED_ACCOUNTS_KEY, sanitized);
    return sanitized;
  };

  const rememberAccount = (user, sessionToken) => {
    const email = String(user?.email || '').trim().toLowerCase();
    const nextToken = String(sessionToken || '').trim();
    if (!email || !nextToken || nextToken === COOKIE_SESSION_TOKEN) return;

    const accountSummary = {
      email,
      name: user?.name || '',
      profile_name: user?.profile?.patient_name || '',
      token: nextToken,
      last_used_at: new Date().toISOString(),
    };

    setSavedAccounts((previous) => {
      const base = Array.isArray(previous) ? previous.filter((item) => item?.email !== email) : [];
      const next = [accountSummary, ...base].slice(0, 8);
      saveCache(SAVED_ACCOUNTS_KEY, next);
      return next;
    });
  };

  const removeSavedAccount = (emailToRemove) => {
    const normalized = String(emailToRemove || '').trim().toLowerCase();
    if (!normalized) return;
    setSavedAccounts((previous) => {
      const next = (Array.isArray(previous) ? previous : []).filter((item) => item?.email !== normalized);
      saveCache(SAVED_ACCOUNTS_KEY, next);
      return next;
    });
  };

  const fetchMe = async () => {
    if (!token && !localStorage.getItem(TOKEN_KEY)) return;
    setAuthHeader(token);
    try {
      const res = await axios.get(`${API_BASE}/auth/me`, getAuthConfig(token));
      setCurrentUser(res.data.user);
      if (res.data.token) {
        localStorage.setItem(TOKEN_KEY, res.data.token);
        setAuthHeader(res.data.token);
        setToken(res.data.token);
        rememberAccount(res.data.user, res.data.token);
      } else if (token && token !== COOKIE_SESSION_TOKEN) {
        rememberAccount(res.data.user, token);
      }
    } catch {
      localStorage.removeItem(TOKEN_KEY);
      setAuthHeader('');
      setToken('');
      setCurrentUser(null);
    }
  };

  const fetchMeds = async () => {
    if (!currentUser) return;
    try {
      const res = await axios.get(`${API_BASE}/me/meds`, getAuthConfig(token));
      setMeds(res.data);
      saveCache(CACHE_MEDS_KEY, res.data);
      setOfflineMode(false);
      setOfflineInfo('');
    } catch {
      const cached = loadCache(CACHE_MEDS_KEY, []);
      setMeds(Array.isArray(cached) ? cached : []);
      setOfflineMode(true);
      setOfflineInfo('You are offline. Showing last synced data.');
    }
  };

  const fetchPrescriptions = async () => {
    if (!currentUser) return;
    try {
      const res = await axios.get(`${API_BASE}/me/prescriptions`, getAuthConfig(token));
      setSavedPrescriptions(res.data);
      saveCache(CACHE_PRESCRIPTIONS_KEY, res.data);
      setOfflineMode(false);
      setOfflineInfo('');
    } catch {
      const cached = loadCache(CACHE_PRESCRIPTIONS_KEY, []);
      setSavedPrescriptions(Array.isArray(cached) ? cached : []);
      setOfflineMode(true);
      setOfflineInfo('You are offline. Showing last synced data.');
    }
  };

  const filteredMeds = meds.filter((med) => med.name.toLowerCase().includes(medSearch.trim().toLowerCase()));
  const profileRequired = Boolean(currentUser) && !Boolean(currentUser.profile_completed);
  const navigateToView = (view, options = {}) => {
    const nextView = VIEW_TO_PATH[view] ? view : 'dashboard';
    const targetPath = VIEW_TO_PATH[nextView];
    const method = options.replace ? 'replaceState' : 'pushState';
    setActiveView(nextView);
    if (window.location.pathname !== targetPath) {
      window.history[method]({}, '', targetPath);
    }
  };

  const requireProfileOrOpen = () => {
    if (!profileRequired) return false;
    navigateToView('profile');
    setProfileError('Please complete your profile to continue.');
    return true;
  };

  const renderHighlightedText = (text, query) => {
    const source = String(text || '');
    const needle = String(query || '').trim();
    if (!needle) return source;

    const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(${escaped})`, 'ig');
    const parts = source.split(regex);
    return parts.map((part, index) => {
      if (part.toLowerCase() === needle.toLowerCase()) {
        return (
          <mark key={`${part}-${index}`} className="bg-amber-200 text-slate-900 rounded px-0.5">
            {part}
          </mark>
        );
      }
      return <span key={`${part}-${index}`}>{part}</span>;
    });
  };

  const getMedicationRiskTag = (medName) => {
    const target = String(medName || '').trim().toLowerCase();
    if (!target) return null;

    const severityRank = { High: 0, Medium: 1, Low: 2 };

    const related = interactions.filter((inter) => {
      const drugA = String(inter?.drug_a || '').toLowerCase();
      const drugB = String(inter?.drug_b || '').toLowerCase();
      return drugA.includes(target) || drugB.includes(target) || target.includes(drugA) || target.includes(drugB);
    }).sort((left, right) => (severityRank[left.severity] ?? 9) - (severityRank[right.severity] ?? 9));

    if (related.length === 0) return null;
    const hasHigh = related.some((inter) => inter.severity === 'High');
    if (hasHigh) {
      return {
        label: 'High risk',
        className: 'bg-red-100 text-red-700 border-red-200',
        interaction: related[0],
      };
    }
    return {
      label: 'Risk',
      className: 'bg-amber-100 text-amber-700 border-amber-200',
      interaction: related[0],
    };
  };

  const openSafetyForInteraction = (interaction) => {
    if (!interaction) return;
    setSelectedSafetyInteraction(interaction);
    navigateToView('safety');
  };

  const openSafetyPage = () => {
    if (requireProfileOrOpen()) return;
    navigateToView('safety');
  };

  const openPremiumUpsell = (context = 'general') => {
    setPremiumContext(context);
    setPremiumModalOpen(true);
  };

  const openUpgradePage = () => {
    setPremiumModalOpen(false);
    navigateToView('upgrade');
  };

  const accountProfiles = Array.isArray(currentUser?.profiles) ? currentUser.profiles : [];
  const activeProfileId = currentUser?.active_profile_id || accountProfiles[0]?.id || 'default';
  const currentAccountEmail = String(currentUser?.email || '').trim().toLowerCase();
  const canAddMoreMedicines = currentUser?.is_premium || meds.length < FREE_TIER_MED_LIMIT;

  const addNewProfile = async (patientName, patientEmail) => {
    if (!currentUser) return;
    if (!currentUser?.is_premium && accountProfiles.length >= FREE_TIER_PROFILE_LIMIT) {
      openPremiumUpsell('profile_limit');
      return false;
    }

    const normalizedName = normalizeWhitespace(sanitizePersonNameInput(patientName, 80));
    const normalizedEmail = String(patientEmail || '').trim().toLowerCase();
    if (!isValidPersonName(normalizedName, { required: true, maxLength: 80 })) {
      setProfileError('Patient name is required and cannot include numbers.');
      return false;
    }
    if (normalizedEmail && !isValidEmail(normalizedEmail)) {
      setProfileError('Please enter a valid patient email.');
      return false;
    }

    setProfileError('');
    setProfileActionLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/me/profiles`, { name: normalizedName, email: normalizedEmail }, getAuthConfig());
      setCurrentUser(res.data.user);
      return true;
    } catch (err) {
      if (err.response?.status === 403) {
        openPremiumUpsell('profile_limit');
      }
      setProfileError(err.response?.data?.detail || 'Could not create a new profile.');
      return false;
    } finally {
      setProfileActionLoading(false);
    }
  };

  const switchProfile = async (profileId) => {
    if (!currentUser || !profileId || profileId === activeProfileId) return;

    setProfileError('');
    setProfileActionLoading(true);
    setProfileSwitching(true);
    try {
      const res = await axios.post(`${API_BASE}/me/profiles/${profileId}/activate`, {}, getAuthConfig());
      setCurrentUser(res.data.user);
      setSelectedSafetyInteraction(null);

      const medsRes = await axios.get(`${API_BASE}/me/meds`, getAuthConfig(token));
      setMeds(Array.isArray(medsRes.data) ? medsRes.data : []);

      const prescriptionsRes = await axios.get(`${API_BASE}/me/prescriptions`, getAuthConfig(token));
      setSavedPrescriptions(Array.isArray(prescriptionsRes.data) ? prescriptionsRes.data : []);

      if (Array.isArray(medsRes.data) && medsRes.data.length >= 2) {
        const safetyRes = await axios.get(`${API_BASE}/me/interactions`, getAuthConfig(token));
        setInteractions(safetyRes.data.interactions || []);
        setSafetyReport(safetyRes.data.report || null);
      } else {
        setInteractions([]);
        setSafetyReport(null);
      }
    } catch (err) {
      setProfileError(err.response?.data?.detail || 'Could not switch profile.');
    } finally {
      setProfileActionLoading(false);
      setProfileSwitching(false);
    }
  };

  const formatPrescriptionDate = (rawDate) => {
    if (!rawDate) return '';
    const parsed = new Date(rawDate);
    if (Number.isNaN(parsed.getTime())) return '';
    return parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatMedicationSource = (source) => {
    const normalized = (source || '').toLowerCase();
    if (!normalized || normalized.includes('prescription')) return 'Prescription';
    if (normalized.includes('ocr')) return 'Prescription';
    if (normalized.includes('over-the-counter') || normalized === 'otc') return 'Over-the-counter';
    if (normalized.includes('supplement') || normalized.includes('vitamin')) return 'Supplement';
    return source;
  };

  const closeOcrReviewModal = () => {
    setOcrResults(null);
    setOcrReviewItems([]);
    setOcrActionInfo('');
    setOcrRecordSaved(false);
    setOcrMedsAdded(false);
  };

  const formatRiskBadge = (inter) => {
    if (inter.kind === 'overdose') return `${inter.severity} Overdose Risk`;
    if (inter.kind === 'duplicate_ingredient') return `${inter.severity} Double-Dose Risk`;
    if (inter.kind === 'duplicate_schedule') return `${inter.severity} Schedule Overlap`;
    if (inter.kind === 'class_overlap') return `${inter.severity} Same-Class Overlap`;
    if (inter.kind === 'dose_sanity') return `${inter.severity} Dose Sanity Alert`;
    return `${inter.severity} Risk`;
  };

  useEffect(() => {
    setAuthHeader(token);
  }, [token]);

  useEffect(() => {
    if (manualLogoutRef.current && !localStorage.getItem(TOKEN_KEY)) {
      setCurrentUser(null);
      setSessionRestorePending(false);
      setAuthHydrated(true);
      return;
    }

    const hydrateAuth = async () => {
      const persistedToken = localStorage.getItem(TOKEN_KEY) || '';

      try {
        setSessionRestorePending(true);
        const res = await axios.get(`${API_BASE}/auth/me`, getAuthConfig(persistedToken));
        setCurrentUser(res.data.user);
        if (res.data.token) {
          localStorage.setItem(TOKEN_KEY, res.data.token);
          setAuthHeader(res.data.token);
          setToken(res.data.token);
          rememberAccount(res.data.user, res.data.token);
        } else if (persistedToken && persistedToken !== COOKIE_SESSION_TOKEN) {
          rememberAccount(res.data.user, persistedToken);
        } else if (!persistedToken) {
          setToken(COOKIE_SESSION_TOKEN);
        }
        manualLogoutRef.current = false;
      } catch (err) {
        const shouldClearSession = err?.response?.status === 401 || err?.response?.status === 403;
        if (shouldClearSession) {
          localStorage.removeItem(TOKEN_KEY);
          setAuthHeader('');
          setToken('');
          setCurrentUser(null);
        }
      } finally {
        setSessionRestorePending(false);
        setAuthHydrated(true);
      }
    };

    setAuthHydrated(false);
    hydrateAuth();
  }, []);

  useEffect(() => {
    const onPopState = () => {
      setActiveView(getViewFromPath(window.location.pathname));
    };

    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  useEffect(() => {
    const initialView = getViewFromPath(window.location.pathname);
    const canonicalPath = VIEW_TO_PATH[initialView] || VIEW_TO_PATH.dashboard;
    if (window.location.pathname !== canonicalPath) {
      window.history.replaceState({}, '', canonicalPath);
    }
  }, []);

  useEffect(() => {
    if (authInterceptorInstalled) return;
    axios.interceptors.request.use((config) => {
      const persistedToken = localStorage.getItem(TOKEN_KEY);
      if (persistedToken && persistedToken !== COOKIE_SESSION_TOKEN) {
        config.headers = config.headers || {};
        config.headers.Authorization = config.headers.Authorization || `Bearer ${persistedToken}`;
      }
      config.withCredentials = true;
      return config;
    });
    authInterceptorInstalled = true;
  }, []);

  useEffect(() => {
    if (authResponseInterceptorInstalled) return;

    axios.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error?.config;
        const status = error?.response?.status;
        const requestUrl = String(originalRequest?.url || '');
        const isAuthEndpoint = /\/api\/auth\/(me|login|register|forgot-password|verify-reset|reset-password|google|logout)/.test(requestUrl);

        // Attempt one silent refresh before forcing logout.
        if (
          status === 401
          && originalRequest
          && !originalRequest._retry
          && !originalRequest._skipAuthRefresh
          && !isAuthEndpoint
        ) {
          originalRequest._retry = true;
          try {
            const res = await axios.get(`${API_BASE}/auth/me`, { withCredentials: true, _skipAuthRefresh: true });
            const refreshedToken = res?.data?.token;
            if (refreshedToken) {
              localStorage.setItem(TOKEN_KEY, refreshedToken);
              setAuthHeader(refreshedToken);
              setToken(refreshedToken);
              originalRequest.headers = originalRequest.headers || {};
              originalRequest.headers.Authorization = `Bearer ${refreshedToken}`;
              return axios(originalRequest);
            }
          } catch {
            localStorage.removeItem(TOKEN_KEY);
            setAuthHeader('');
            setToken('');
            setCurrentUser(null);
          }
        }

        return Promise.reject(error);
      }
    );

    authResponseInterceptorInstalled = true;
  }, []);

  useEffect(() => {
    if (currentUser) {
      fetchMeds();
      fetchPrescriptions();
      const existingProfile = currentUser.profile || {};
      setProfileForm((prev) => ({
        ...prev,
        patient_name: existingProfile.patient_name || '',
        patient_email: existingProfile.patient_email || '',
        age: existingProfile.age ? String(existingProfile.age) : '',
        gender_identity: existingProfile.gender_identity || '',
        weight_kg: existingProfile.weight_kg ? String(existingProfile.weight_kg) : '',
        height_cm: existingProfile.height_cm ? String(existingProfile.height_cm) : '',
        chronic_conditions_text: (existingProfile.chronic_conditions || []).join(', '),
        allergies_text: (existingProfile.allergies || []).join(', '),
        kidney_disease: Boolean(existingProfile.kidney_disease),
        liver_disease: Boolean(existingProfile.liver_disease),
        smoking_status: existingProfile.smoking_status || 'unknown',
        alcohol_use: existingProfile.alcohol_use || 'unknown',
        grapefruit_use: existingProfile.grapefruit_use || 'unknown',
        dairy_use: existingProfile.dairy_use || 'unknown',
        egfr: existingProfile.egfr ? String(existingProfile.egfr) : '',
        alt_u_l: existingProfile.alt_u_l ? String(existingProfile.alt_u_l) : '',
        ast_u_l: existingProfile.ast_u_l ? String(existingProfile.ast_u_l) : '',
        inr: existingProfile.inr ? String(existingProfile.inr) : '',
        glucose_mg_dl: existingProfile.glucose_mg_dl ? String(existingProfile.glucose_mg_dl) : '',
        emergency_contact_name: existingProfile.emergency_contact_name || '',
        emergency_contact_phone: existingProfile.emergency_contact_phone || '',
        emergency_notes: existingProfile.emergency_notes || '',
        care_team_patients: Array.isArray(existingProfile.care_team_patients) ? existingProfile.care_team_patients : [],
        privacy_consent: Boolean(currentUser.privacy_consent),
      }));
      if (activeView === 'profile' && currentUser.profile_completed) {
        setProfileError('');
      }
    }
  }, [currentUser, activeView]);

  useEffect(() => {
    if (!authHydrated || !currentUser) return;

    if (currentUser.profile_completed) {
      setProfileNudgeVisible(false);
      hasShownProfileNudgeRef.current = true;
      return;
    }

    if (
      activeView === 'dashboard'
      && !hasShownProfileNudgeRef.current
    ) {
      setProfileNudgeVisible(true);
      hasShownProfileNudgeRef.current = true;
    }

    if (activeView === 'profile') {
      setProfileNudgeVisible(false);
    }
  }, [activeView, authHydrated, currentUser]);

  useEffect(() => {
    if (!currentUser || !authHydrated) return;
    if (meds.length < 2) {
      setInteractions([]);
      setSafetyReport(null);
      return;
    }

    // Rebuild safety data after app refresh/login so profile risk badges persist.
    scheduleSafetyRefresh();
  }, [currentUser, authHydrated, meds.length]);

  useEffect(() => {
    if (currentUser || !authHydrated) return;
    if (!token && !localStorage.getItem(TOKEN_KEY)) return;
    
    const retryTimer = setTimeout(() => {
      fetchMe();
    }, 1500);
    return () => clearTimeout(retryTimer);
  }, [token, currentUser, authHydrated]);

  useEffect(() => {
    const fetchAuthMeta = async () => {
      try {
        const res = await axios.get(`${API_BASE}/auth/meta`);
        setMinPasswordLength(res.data.min_password_length || 8);
        setGoogleEnabled(Boolean(res.data.google_enabled) && Boolean(GOOGLE_CLIENT_ID));
      } catch {
        setMinPasswordLength(8);
      }
    };
    fetchAuthMeta();
  }, []);

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    const paymentSuccess = urlParams.get('payment_success');

    if (paymentSuccess && sessionId && authHydrated && currentUser) {
      const verifyPayment = async () => {
        try {
          await axios.post(`${API_BASE}/payments/verify-session`, { session_id: sessionId }, getAuthConfig(token));
          fetchMe();
          window.history.replaceState({}, document.title, window.location.pathname);
          setCongratsModalOpen(true);
        } catch (err) {
          console.error("Payment verification failed", err);
        }
      };
      verifyPayment();
    }
  }, [authHydrated, currentUser, token]);

  useEffect(() => {
    if (token || !googleEnabled || !GOOGLE_CLIENT_ID || authMode === 'forgot') {
      setGoogleButtonReady(false);
      setGoogleUiError('');
      googleRenderedRef.current = false;
      return;
    }

    let cancelled = false;
    setGoogleButtonReady(false);
    setGoogleUiError('');

    const loadingTimeout = setTimeout(() => {
      if (!cancelled && !googleRenderedRef.current) {
        setGoogleUiError('Google button could not load. Check OAuth Authorized JavaScript origins.');
      }
    }, 6000);

    const mountGoogleButton = () => {
      if (cancelled) return false;
      const target = googleSlotRef.current;
      if (!target || !window.google?.accounts?.id) return false;

      try {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: async (response) => {
            setGoogleAuthLoading(true);
            setAuthLoading(true);
            setAuthError('');
            setAuthInfo('');
            try {
              const res = await axios.post(`${API_BASE}/auth/google`, { idToken: response.credential });
              localStorage.setItem(TOKEN_KEY, res.data.token);
              setAuthHeader(res.data.token);
              setToken(res.data.token);
              setCurrentUser(res.data.user);
              rememberAccount(res.data.user, res.data.token);
              setAuthHydrated(true);
            } catch (err) {
              setAuthError(err.response?.data?.detail || 'Google sign-in failed');
            } finally {
              setGoogleAuthLoading(false);
              setAuthLoading(false);
            }
          },
        });

        target.innerHTML = '';
        window.google.accounts.id.renderButton(target, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'pill',
          width: 340,
        });
        googleRenderedRef.current = true;
        setGoogleButtonReady(true);
        setGoogleUiError('');
        return true;
      } catch (e) {
        googleRenderedRef.current = false;
        setGoogleButtonReady(false);
        setGoogleUiError('Google sign-in failed to render. Verify your client ID and browser origin.');
        return false;
      }
    };

    const retryMountGoogleButton = (attempt = 0) => {
      if (cancelled) return;
      if (mountGoogleButton()) return;
      if (attempt < 20) {
        window.requestAnimationFrame(() => retryMountGoogleButton(attempt + 1));
      }
    };

    const existing = document.getElementById('google-identity-script');
    if (existing) {
      retryMountGoogleButton();
      return () => {
        cancelled = true;
        clearTimeout(loadingTimeout);
      };
    }

    const script = document.createElement('script');
    script.id = 'google-identity-script';
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (!cancelled) retryMountGoogleButton();
    };
    script.onerror = () => {
      if (!cancelled) {
        setGoogleUiError('Failed to load Google script. Check internet connection or browser extensions.');
      }
    };
    document.body.appendChild(script);

    return () => {
      cancelled = true;
      clearTimeout(loadingTimeout);
    };
  }, [token, googleEnabled, authMode]);

  const clearAuthMessages = () => {
    setAuthError('');
    setAuthInfo('');
  };

  const switchAuthMode = (mode) => {
    setAuthMode(mode);
    clearAuthMessages();
    setAuthPassword('');
    setConfirmPassword('');
    setConfirmNewPassword('');
    setResetCode('');
    setNewPassword('');
    setForgotOtpSent(false);
    setForgotOtpVerified(false);
    setShowAuthPassword(false);
    setAuthRole('patient');
  };

  const validateEmail = (email) => isValidEmail(email);
  
  const validatePassword = (password, minLength) => {
    if (!password || password.length < minLength) return false;
    return true;
  };

  const validateDrugName = (name) => {
    const trimmed = normalizeWhitespace(name);
    if (!trimmed) return { valid: false, error: 'Drug name is required.' };
    if (!isValidPersonName(trimmed, { required: true, maxLength: 200 })) {
      return { valid: false, error: 'Medicine name can only contain letters, spaces, apostrophes, dots, and hyphens.' };
    }
    if (trimmed.length > 200) return { valid: false, error: 'Drug name must be 200 characters or less.' };
    return { valid: true };
  };

  const validateDose = (dose) => {
    const trimmed = normalizeWhitespace(dose);
    if (!trimmed) return { valid: true }; // Optional field
    if (trimmed.length > 100) return { valid: false, error: 'Dose must be 100 characters or less.' };
    if (!/^[A-Za-z0-9\s.,/%()-]+$/.test(trimmed)) {
      return { valid: false, error: 'Dose contains invalid characters.' };
    }
    if (/(^|[\s(])-\s*\d/.test(trimmed)) {
      return { valid: false, error: 'Dose cannot contain negative values.' };
    }
    return { valid: true };
  };

  const validateFrequency = (frequency) => {
    const trimmed = normalizeWhitespace(frequency);
    if (!trimmed) return { valid: true }; // Optional field
    if (trimmed.length > 100) return { valid: false, error: 'Frequency must be 100 characters or less.' };
    if (!/^[A-Za-z0-9\s.,/()-]+$/.test(trimmed)) {
      return { valid: false, error: 'Frequency contains invalid characters.' };
    }
    if (/(^|[\s(])-\s*\d/.test(trimmed)) {
      return { valid: false, error: 'Frequency cannot contain negative values.' };
    }
    return { valid: true };
  };

  const validateProfilePayload = (form) => {
    const patientName = normalizeWhitespace(form.patient_name);
    if (!isValidPersonName(patientName, { required: true, maxLength: 120 })) {
      return 'Patient name is required and cannot contain numbers.';
    }

    const patientEmail = String(form.patient_email || '').trim().toLowerCase();
    if (patientEmail && !isValidEmail(patientEmail)) {
      return 'Patient email must be a valid email address.';
    }

    const chronicConditions = parseCsvList(form.chronic_conditions_text);
    const allergies = parseCsvList(form.allergies_text);
    const descriptorLists = [
      { label: 'Chronic condition', values: chronicConditions },
      { label: 'Allergy', values: allergies },
    ];
    for (const list of descriptorLists) {
      for (const entry of list.values) {
        const item = normalizeWhitespace(entry);
        if (!item) continue;
        if (/(^|\s)-\s*\d/.test(item) || /^-?\d+(?:\.\d+)?$/.test(item)) {
          return `${list.label} entries cannot be negative numbers.`;
        }
        if (!/[A-Za-z]/.test(item)) {
          return `${list.label} entries must contain descriptive text.`;
        }
      }
    }

    const age = parseNumberField(form.age);
    if (!Number.isFinite(age) || age < 0 || age > 120 || !Number.isInteger(age)) {
      return 'Age must be a whole number between 0 and 120.';
    }

    const boundedNumbers = [
      { key: 'weight_kg', min: 0, max: 400, label: 'Weight' },
      { key: 'height_cm', min: 0, max: 260, label: 'Height' },
      { key: 'egfr', min: 0, max: 300, label: 'eGFR' },
      { key: 'alt_u_l', min: 0, max: 5000, label: 'ALT' },
      { key: 'ast_u_l', min: 0, max: 5000, label: 'AST' },
      { key: 'inr', min: 0, max: 20, label: 'INR' },
      { key: 'glucose_mg_dl', min: 0, max: 2000, label: 'Glucose' },
    ];

    for (const field of boundedNumbers) {
      const value = parseNumberField(form[field.key]);
      if (value !== null && (!Number.isFinite(value) || value < field.min || value > field.max)) {
        return `${field.label} must be between ${field.min} and ${field.max}.`;
      }
    }

    const emergencyContactName = normalizeWhitespace(form.emergency_contact_name);
    if (emergencyContactName && !isValidPersonName(emergencyContactName, { required: false, maxLength: 120 })) {
      return 'Emergency contact name cannot contain numbers.';
    }

    const careTeamPatients = Array.isArray(form.care_team_patients) ? form.care_team_patients : [];
    for (const patient of careTeamPatients) {
      const name = normalizeWhitespace(patient?.name);
      const email = String(patient?.email || '').trim().toLowerCase();
      if (!name || !isValidPersonName(name, { required: true, maxLength: 120 })) {
        return 'Each caregiver patient name must contain letters only.';
      }
      if (email && !isValidEmail(email)) {
        return 'Each caregiver patient email must be valid.';
      }
    }

    return null;
  };

  const validateFile = (file) => {
    if (!file) return { valid: false, error: 'Please select a file.' };
    
    const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'application/pdf'];
    if (!validTypes.includes(file.type)) {
      return { valid: false, error: 'Only PNG, JPG, and PDF files are allowed.' };
    }
    
    const maxSize = 10 * 1024 * 1024; // 10MB
    if (file.size > maxSize) {
      return { valid: false, error: 'File size must be 10MB or less.' };
    }
    
    return { valid: true };
  };

  const handleAuthSubmit = async () => {
    clearAuthMessages();

    const email = authEmail.trim().toLowerCase();
    if (!email) {
      setAuthError('Email is required.');
      return;
    }
    if (!validateEmail(email)) {
      setAuthError('Please enter a valid email address.');
      return;
    }

    if (
      !email ||
      (authMode !== 'forgot' && !authPassword.trim()) ||
      (authMode === 'register' && !authName.trim())
    ) {
      setAuthError('Please fill all required fields.');
      return;
    }

    if (authMode !== 'forgot' && authPassword.length < minPasswordLength) {
      setAuthError(`Password must be at least ${minPasswordLength} characters.`);
      return;
    }

    if (authMode === 'register' && authPassword !== confirmPassword) {
      setAuthError('Password and confirm password do not match.');
      return;
    }

    if (authMode === 'register' && !isValidPersonName(authName, { required: true, maxLength: 120 })) {
      setAuthError('Name must contain letters only and cannot include numbers.');
      return;
    }

    setAuthLoading(true);
    try {
      if (authMode === 'forgot') {
        await axios.post(`${API_BASE}/auth/forgot-password`, { email });
        setAuthInfo('If this email exists, OTP has been sent. Enter it below to reset your password.');
        setForgotOtpSent(true);
        setForgotOtpVerified(false);
      } else {
        const url = authMode === 'register' ? `${API_BASE}/auth/register` : `${API_BASE}/auth/login`;
        const payload = authMode === 'register'
          ? { name: authName.trim(), email, password: authPassword, role: authRole }
          : { email, password: authPassword };

        const res = await axios.post(url, payload);
        localStorage.setItem(TOKEN_KEY, res.data.token);
        setAuthHeader(res.data.token);
        setToken(res.data.token);
        setCurrentUser(res.data.user);
        rememberAccount(res.data.user, res.data.token);
        setAuthHydrated(true);
        setAuthPassword('');
        setConfirmPassword('');
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.message || 'Authentication failed';
      if (authMode === 'login' && msg.toLowerCase().includes('invalid email or password')) {
        setAuthError('Invalid email or password. Use Forgot Password to reset access.');
      } else {
        setAuthError(msg);
      }
    } finally {
      setAuthLoading(false);
    }
  };

  const handleVerifyOtp = async () => {
    clearAuthMessages();
    if (!authEmail.trim() || !resetCode.trim()) return;
    setAuthLoading(true);
    try {
      await axios.post(`${API_BASE}/auth/verify-reset`, {
        email: authEmail.trim(),
        code: resetCode.trim(),
      });
      setAuthInfo('OTP verified. You can now set a new password.');
      setForgotOtpVerified(true);
      setForgotOtpSent(false);
      setAuthError('');
    } catch (err) {
      setAuthError(err.response?.data?.detail || 'OTP verification failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const handleResetPassword = async () => {
    clearAuthMessages();
    if (!authEmail.trim() || !resetCode.trim() || !newPassword.trim() || !confirmNewPassword.trim()) return;
    if (newPassword.length < minPasswordLength) {
      setAuthError(`New password must be at least ${minPasswordLength} characters.`);
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setAuthError('New password and confirm password do not match.');
      return;
    }

    setAuthLoading(true);
    try {
      await axios.post(`${API_BASE}/auth/reset-password`, {
        email: authEmail.trim(),
        code: resetCode.trim(),
        new_password: newPassword,
      });
      switchAuthMode('login');
      setAuthInfo('Password reset successful. Please sign in.');
      setAuthPassword('');
      setNewPassword('');
      setConfirmNewPassword('');
      setResetCode('');
    } catch (err) {
      setAuthError(err.response?.data?.detail || 'Password reset failed');
    } finally {
      setAuthLoading(false);
    }
  };

  const submitProfile = async () => {
    setProfileError('');
    const profileValidationError = validateProfilePayload(profileForm);
    if (profileValidationError) {
      setProfileError(profileValidationError);
      return;
    }

    setProfileSaving(true);
    try {
      const payload = {
        age: Number(profileForm.age || 0),
        gender_identity: normalizeWhitespace(profileForm.gender_identity),
        weight_kg: Number(profileForm.weight_kg || 0),
        height_cm: Number(profileForm.height_cm || 0),
        chronic_conditions: parseCsvList(profileForm.chronic_conditions_text).map((item) => normalizeWhitespace(item)),
        allergies: parseCsvList(profileForm.allergies_text).map((item) => normalizeWhitespace(item)),
        kidney_disease: Boolean(profileForm.kidney_disease),
        liver_disease: Boolean(profileForm.liver_disease),
        smoking_status: profileForm.smoking_status,
        alcohol_use: profileForm.alcohol_use,
        grapefruit_use: profileForm.grapefruit_use,
        dairy_use: profileForm.dairy_use,
        egfr: Number(profileForm.egfr || 0),
        alt_u_l: Number(profileForm.alt_u_l || 0),
        ast_u_l: Number(profileForm.ast_u_l || 0),
        inr: Number(profileForm.inr || 0),
        glucose_mg_dl: Number(profileForm.glucose_mg_dl || 0),
        emergency_contact_name: normalizeWhitespace(profileForm.emergency_contact_name),
        emergency_contact_phone: String(profileForm.emergency_contact_phone || '').trim(),
        emergency_notes: String(profileForm.emergency_notes || '').trim(),
        care_team_patients: profileForm.care_team_patients,
        privacy_consent: Boolean(profileForm.privacy_consent),
        patient_name: normalizeWhitespace(profileForm.patient_name),
        patient_email: String(profileForm.patient_email || '').trim().toLowerCase(),
      };

      const res = await axios.put(`${API_BASE}/me/profile`, payload, getAuthConfig());
      setCurrentUser(res.data.user);
      setProfileError('');
    } catch (err) {
      setProfileError(err.response?.data?.detail || 'Could not save profile.');
    } finally {
      setProfileSaving(false);
    }
  };

  const deleteMyAccount = async (confirmEmail = '') => {
    setDeleteAccountLoading(true);
    try {
      await axios.delete(`${API_BASE}/me/privacy/delete-account`, {
        ...getAuthConfig(),
        data: {
          confirm_text: deleteAccountText,
          confirm_email: confirmEmail,
        },
      });
      executeLogout({ clearOnlyCurrentAccount: true });
      setDeleteAccountText('');
    } catch (err) {
      alert(err.response?.data?.detail || 'Could not delete account.');
    } finally {
      setDeleteAccountLoading(false);
    }
  };

  const executeLogout = async ({ clearOnlyCurrentAccount = false } = {}) => {
    manualLogoutRef.current = true;
    await axios.post(`${API_BASE}/auth/logout`, {}, { withCredentials: true }).catch(() => {});

    if (clearOnlyCurrentAccount && currentUser?.email) {
      removeSavedAccount(currentUser.email);
    }

    localStorage.removeItem(TOKEN_KEY);
    setAuthHeader('');
    setToken('');
    setCurrentUser(null);
    setAuthHydrated(true);
    setMeds([]);
    setInteractions([]);
    setSafetyReport(null);
    setSavedPrescriptions([]);
    setOcrResults(null);
    setOcrReviewItems([]);
    setMedSearch('');
    setManualDrugType(MANUAL_SOURCE_DEFAULT);
    setManualDose('');
    setManualFrequency('');
    setManualError('');
    setUploadedFileName('');
    setRawText('');
    setOcrRecordSaved(false);
    setOcrMedsAdded(false);
    setOcrActionInfo('');
    setSelectedSafetyInteraction(null);
    setOfflineMode(false);
    setOfflineInfo('');
    setProfileError('');
    setPendingEditMed(null);
    setAccountSwitcherOpen(false);
    setSwitchingAccountEmail('');
    if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
    setFilePreviewOpen(false);
    setFilePreviewLoading(false);
    setFilePreviewUrl('');
    setFilePreviewName('');
    setFilePreviewMime('');
    navigateToView('dashboard', { replace: true });
    setPrescriptionModalOpen(false);
    setSidebarOpen(true);
  };

  const requestLogout = () => {
    setLogoutConfirmOpen(true);
  };

  const confirmLogout = async () => {
    setLogoutConfirmOpen(false);
    setLoggingOut(true);
    await new Promise((resolve) => setTimeout(resolve, 260));
    await executeLogout();
    await new Promise((resolve) => setTimeout(resolve, 260));
    setLoggingOut(false);
  };

  const switchSavedAccount = async (account) => {
    const nextToken = String(account?.token || '').trim();
    if (!nextToken) return;

    setSwitchingAccountEmail(account.email || '');
    try {
      localStorage.setItem(TOKEN_KEY, nextToken);
      setAuthHeader(nextToken);
      setToken(nextToken);
      const res = await axios.get(`${API_BASE}/auth/me`, getAuthConfig(nextToken));
      setCurrentUser(res.data.user);
      if (res.data.token) {
        localStorage.setItem(TOKEN_KEY, res.data.token);
        setAuthHeader(res.data.token);
        setToken(res.data.token);
        rememberAccount(res.data.user, res.data.token);
      } else {
        rememberAccount(res.data.user, nextToken);
      }
      setAccountSwitcherOpen(false);
      clearAuthMessages();
    } catch {
      removeSavedAccount(account.email);
      if (currentUser?.email === account.email) {
        await executeLogout();
      }
      setAuthError('Could not switch to that account. Please sign in again.');
    } finally {
      setSwitchingAccountEmail('');
    }
  };

  const uploadFile = async (file) => {
    if (requireProfileOrOpen()) return;
    if (!file || !token) {
      setManualError('No file selected. Please try again.');
      return;
    }
    
    // Validate file
    const fileValidation = validateFile(file);
    if (!fileValidation.valid) {
      setManualError(fileValidation.error);
      return;
    }
    
    setIsUploading(true);
    setUploadStage('uploading');
    setManualError('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploadStage('analyzing');
      const res = await axios.post(`${API_BASE}/me/upload`, formData);
      const results = res.data.drugs || [];
      setUploadStage(res.data?.timings?.validation_mode === 'deferred' ? 'reviewing' : 'completed');
      setOcrResults(results);
      setOcrReviewItems(results.map((drug) => ({
        ...drug,
        draftName: drug.name,
        draftDose: drug.dose || '',
        draftFrequency: drug.frequency || '',
        include: !Boolean(drug.duplicate_in_profile),
      })));
      setRawText(res.data.raw_text || '');
      setUploadedFileName(res.data.uploaded_file_name || '');
      setOcrConfidence(res.data.confidence || 0);
      setOcrRecordSaved(false);
      setOcrMedsAdded(false);
      const duplicateMeds = Number(res.data?.flags?.duplicate_medicines_count || 0);
      const duplicateRx = Boolean(res.data?.flags?.duplicate_prescription_exact);
      if (duplicateRx || duplicateMeds > 0) {
        const notices = [];
        if (duplicateRx) notices.push('This prescription appears to already exist in your history.');
        if (duplicateMeds > 0) notices.push(`${duplicateMeds} medicine${duplicateMeds === 1 ? '' : 's'} already exist in this profile and were pre-marked as skip.`);
        setOcrActionInfo(notices.join(' '));
      } else {
        setOcrActionInfo('');
      }
      if (res.data?.timings) {
        console.info('Prescription processing timings', res.data.timings);
      }
    } catch (err) {
      setManualError(err.response?.data?.detail || err.response?.data?.message || 'Upload failed. Please check the file and try again.');
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadStage('idle'), 500);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    await uploadFile(file);
  };

  const handleDropUpload = async (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    await uploadFile(file);
  };

  const updateReviewedDrug = (index, key, value) => {
    const normalizedValue = (() => {
      if (key === 'draftName') return sanitizeMedicationNameInput(value, 200);
      if (key === 'draftDose') return sanitizeDoseInput(value, 100);
      if (key === 'draftFrequency') return sanitizeFrequencyInput(value, 100);
      return value;
    })();

    setOcrReviewItems((previous) => previous.map((item, itemIndex) => (
      itemIndex === index ? { ...item, [key]: normalizedValue } : item
    )));
  };

  const confirmDrug = async (drug) => {
    if (drug?.duplicate_in_profile || drug?.action === 'skip') {
      const name = drug.draftName || drug.name || 'This medicine';
      setManualError('');
      setOcrActionInfo(`Skipped ${name} because it is already in this profile.`);
      setOcrReviewItems((previous) => previous.map((item) => (
        item.name === drug.name ? { ...item, include: false, action: 'skip', match_status: 'duplicate_in_profile' } : item
      )));
      return { status: 'skipped_duplicate', name };
    }

    if (!canAddMoreMedicines) {
      openPremiumUpsell('medicine_limit');
      return { status: 'blocked_limit' };
    }

    const incomingKey = normalizeMedicationDuplicateKey(drug.draftName || drug.name || '');
    const duplicateExists = meds.some((med) => normalizeMedicationDuplicateKey(med.name) === incomingKey);
    if (duplicateExists) {
      setManualError('');
      setOcrActionInfo(`Skipped ${drug.draftName || drug.name || 'this medicine'} because it is already in this profile.`);
      setOcrReviewItems((previous) => previous.map((item) => (
        item.name === drug.name ? { ...item, include: false, action: 'skip', match_status: 'duplicate_in_profile', duplicate_in_profile: true } : item
      )));
      return { status: 'skipped_duplicate', name: drug.draftName || drug.name || '' };
    }

    const drugNameValidation = validateDrugName(drug.draftName || drug.name || '');
    if (!drugNameValidation.valid) {
      setManualError(drugNameValidation.error);
      return { status: 'validation_error', message: drugNameValidation.error };
    }
    
    const doseValidation = validateDose(drug.draftDose || '');
    if (!doseValidation.valid) {
      setManualError(doseValidation.error);
      return { status: 'validation_error', message: doseValidation.error };
    }
    
    const frequencyValidation = validateFrequency(drug.draftFrequency || '');
    if (!frequencyValidation.valid) {
      setManualError(frequencyValidation.error);
      return { status: 'validation_error', message: frequencyValidation.error };
    }

    try {
      const drugName = (drug.draftName || drug.name || '').trim();
      await axios.post(`${API_BASE}/me/add`, {
        drug_name: drugName,
        rxcui: drug.rxcui || 'N/A',
        dose: (drug.draftDose || '').trim(),
        frequency: (drug.draftFrequency || '').trim(),
        source: 'Prescription medicine',
        prescription_file_name: uploadedFileName,
      }, getAuthConfig());
      setOcrResults((prev) => prev.filter((d) => d.name !== drug.name));
      setOcrReviewItems((prev) => prev.filter((d) => d.name !== drug.name));
      setManualError('');
      await fetchMeds();
      scheduleSafetyRefresh();
      return { status: 'added', name: drugName };
    } catch (err) {
      if (err.response?.status === 401) {
        await executeLogout();
        setAuthError('Session expired. Please sign in again.');
        return { status: 'auth_error' };
      }
      if (err.response?.status === 409) {
        setManualError('');
        setOcrActionInfo(`${drug.draftName || drug.name || 'This medicine'} is already in this profile and was skipped.`);
        setOcrReviewItems((prev) => prev.map((item) => (
          item.name === drug.name ? { ...item, include: false, action: 'skip', match_status: 'duplicate_in_profile', duplicate_in_profile: true } : item
        )));
        return { status: 'skipped_duplicate', name: drug.draftName || drug.name || '' };
      }
      setManualError(err.response?.data?.detail || err.response?.data?.message || 'Failed to add medication from OCR.');
      return { status: 'error', message: err.response?.data?.detail || err.response?.data?.message || 'Failed to add medication from OCR.' };
    }
  };

  const confirmAllReviewedDrugs = async () => {
    const candidates = ocrReviewItems.filter((drug) => drug.include && (drug.draftName || '').trim());
    if (candidates.length === 0) {
      const duplicateOnlyCount = ocrReviewItems.filter((item) => item.duplicate_in_profile || item.action === 'skip').length;
      if (duplicateOnlyCount > 0) {
        setOcrActionInfo(`No new medicines to add. ${duplicateOnlyCount} medicine${duplicateOnlyCount === 1 ? '' : 's'} already exist in this profile.`);
      }
      return;
    }

    const freeSlots = FREE_TIER_MED_LIMIT - meds.length;
    if (!currentUser?.is_premium && (freeSlots <= 0 || candidates.length > freeSlots)) {
      openPremiumUpsell('medicine_limit');
      return;
    }

    setBulkAddLoading(true);
    setOcrActionInfo('');
    try {
      let addedCount = 0;
      let skippedDuplicateCount = 0;
      let validationErrorCount = 0;
      let failedCount = 0;

      for (const drug of candidates) {
        // eslint-disable-next-line no-await-in-loop
        const outcome = await confirmDrug(drug);
        if (outcome?.status === 'added') addedCount += 1;
        else if (outcome?.status === 'skipped_duplicate') skippedDuplicateCount += 1;
        else if (outcome?.status === 'validation_error') validationErrorCount += 1;
        else if (outcome?.status === 'error') failedCount += 1;
      }
      setOcrMedsAdded(addedCount > 0);

      const summary = [];
      if (addedCount > 0) summary.push(`${addedCount} added`);
      if (skippedDuplicateCount > 0) summary.push(`${skippedDuplicateCount} skipped as duplicates`);
      if (validationErrorCount > 0) summary.push(`${validationErrorCount} need review`);
      if (failedCount > 0) summary.push(`${failedCount} failed`);

      if (summary.length === 0) {
        setOcrActionInfo('No medicines were added.');
      } else {
        setOcrActionInfo(`Medicine add summary: ${summary.join(' | ')}.`);
      }

      scheduleSafetyRefresh();
      if (ocrRecordSaved) {
        closeOcrReviewModal();
      }
    } finally {
      setBulkAddLoading(false);
    }
  };

  const handleManualAdd = async () => {
    if (requireProfileOrOpen()) {
      setManualError('Complete your profile before adding medicines.');
      return;
    }

    if (!canAddMoreMedicines) {
      setManualError('Free tier supports up to 6 medicines. Upgrade to add more.');
      openPremiumUpsell('medicine_limit');
      return;
    }

    setManualError('');
    
    // Check for duplicate medication (case-insensitive)
    const normalizedDrugName = normalizeWhitespace(sanitizeMedicationNameInput(manualDrugName));
    const normalizedInput = normalizeMedicationDuplicateKey(normalizedDrugName);
    const duplicateExists = meds.some((med) => normalizeMedicationDuplicateKey(med.name) === normalizedInput);
    if (duplicateExists) {
      setManualError(`${normalizedDrugName} is already in your medication profile. Edit or delete the existing entry if you need to update it.`);
      return;
    }
    
    // Validate drug name
    const drugNameValidation = validateDrugName(normalizedDrugName);
    if (!drugNameValidation.valid) {
      setManualError(drugNameValidation.error);
      return;
    }
    
    // Validate dose if provided
    const normalizedDose = normalizeWhitespace(sanitizeDoseInput(manualDose));
    const doseValidation = validateDose(normalizedDose);
    if (!doseValidation.valid) {
      setManualError(doseValidation.error);
      return;
    }
    
    // Validate frequency if provided
    const normalizedFrequency = normalizeWhitespace(sanitizeFrequencyInput(manualFrequency));
    const frequencyValidation = validateFrequency(normalizedFrequency);
    if (!frequencyValidation.valid) {
      setManualError(frequencyValidation.error);
      return;
    }

    setManualSaving(true);
    try {
      await axios.post(`${API_BASE}/me/add`, {
        drug_name: normalizedDrugName,
        rxcui: 'N/A',
        source: manualDrugType,
        dose: normalizedDose,
        frequency: normalizedFrequency,
      }, getAuthConfig());
      setManualDrugName('');
      setManualDose('');
      setManualFrequency('');
      setManualError('');
      await fetchMeds();
      scheduleSafetyRefresh();
    } catch (err) {
      if (err.response?.status === 401) {
        await executeLogout();
        setAuthError('Session expired. Please sign in again.');
        return;
      }
      if (err.response?.status === 409) {
        setManualError(err.response?.data?.detail || 'This medicine already appears in the profile or is a close duplicate.');
        return;
      }
      setManualError(err.response?.data?.detail || err.response?.data?.message || 'Failed to add medication. Please try again.');
    } finally {
      setManualSaving(false);
    }
  };

  const deleteMed = async (id) => {
    if (!id) return;
    setPendingDeleteMedId(id);
  };

  const openEditMed = (med) => {
    if (!med) return;
    setPendingEditMed(med);
    setEditMedName(med.name || '');
    setEditMedType(med.source || MANUAL_SOURCE_DEFAULT);
    setEditMedDose(med.dose || '');
    setEditMedFrequency(med.frequency || '');
  };

  const submitEditMed = async () => {
    if (!pendingEditMed?.id) return;
    const normalizedName = normalizeWhitespace(sanitizeMedicationNameInput(editMedName));
    const normalizedDose = normalizeWhitespace(sanitizeDoseInput(editMedDose));
    const normalizedFrequency = normalizeWhitespace(sanitizeFrequencyInput(editMedFrequency));

    const nameValidation = validateDrugName(normalizedName);
    if (!nameValidation.valid) {
      setManualError(nameValidation.error);
      return;
    }

    const doseValidation = validateDose(normalizedDose);
    if (!doseValidation.valid) {
      setManualError(doseValidation.error);
      return;
    }

    const frequencyValidation = validateFrequency(normalizedFrequency);
    if (!frequencyValidation.valid) {
      setManualError(frequencyValidation.error);
      return;
    }

    try {
      setUpdateMedLoading(true);
      await axios.put(
        `${API_BASE}/me/meds/${pendingEditMed.id}`,
        {
          drug_name: normalizedName,
          source: editMedType,
          dose: normalizedDose,
          frequency: normalizedFrequency,
        },
        getAuthConfig()
      );
      setPendingEditMed(null);
      await fetchMeds();
      scheduleSafetyRefresh();
    } catch (err) {
      setManualError(err.response?.data?.detail || 'Could not update this medicine.');
    } finally {
      setUpdateMedLoading(false);
    }
  };

  const confirmDeleteMed = async (medId) => {
    if (!medId) return;
    try {
      setDeleteMedLoading(true);
      await axios.delete(`${API_BASE}/me/meds/${medId}`, getAuthConfig());
      await fetchMeds();
      setPendingDeleteMedId(null);
      scheduleSafetyRefresh();
    } catch (err) {
      if (err.response?.status === 401) {
        await executeLogout();
        setAuthError('Session expired. Please sign in again.');
        return;
      }
      alert(err.response?.data?.detail || 'Could not delete this medicine.');
    } finally {
      setDeleteMedLoading(false);
    }
  };

  const checkSafety = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/me/interactions`, getAuthConfig());
      setInteractions(res.data.interactions || []);
      setSafetyReport(res.data.report || null);
      saveCache(CACHE_SAFETY_KEY, {
        interactions: res.data.interactions || [],
        report: res.data.report || null,
      });
      if (res.data.degraded_mode) {
        setOfflineInfo('Clinical API timed out. Showing local safety checks only.');
      } else {
        setOfflineInfo('');
      }
      setOfflineMode(Boolean(res.data.degraded_mode));
    } catch (err) {
      if (err.response?.status === 401) {
        await executeLogout();
        setAuthError('Session expired. Please sign in again.');
        return;
      }
      const cached = loadCache(CACHE_SAFETY_KEY, { interactions: [], report: null });
      setInteractions(cached?.interactions || []);
      setSafetyReport(cached?.report || null);
      setOfflineMode(true);
      setOfflineInfo('Safety service unavailable. Showing last synced safety report.');
      setManualError(err.response?.data?.detail || 'Failed to check safety.');
    } finally {
      setLoading(false);
    }
  };

  const scheduleSafetyRefresh = () => {
    if (safetyRefreshTimerRef.current) {
      clearTimeout(safetyRefreshTimerRef.current);
    }
    safetyRefreshTimerRef.current = setTimeout(() => {
      checkSafety();
    }, 250);
  };

  const savePrescriptionRecord = async () => {
    if (!rawText.trim()) return;

    if (!currentUser?.is_premium && savedPrescriptions.length >= FREE_TIER_PRESCRIPTION_LIMIT) {
      openPremiumUpsell('prescription_limit');
      return;
    }

    setRecordSaving(true);
    try {
      const response = await axios.post(`${API_BASE}/me/prescriptions`, {
        raw_text: rawText,
        confidence: ocrConfidence,
        uploaded_file_name: uploadedFileName,
      }, getAuthConfig());

      if (response.data?.status === 'already_exists') {
        setOcrRecordSaved(true);
        setOcrActionInfo(response.data?.warning?.message || 'This prescription is already saved.');
        return;
      }

      await fetchPrescriptions();
      setOcrRecordSaved(true);
      setOcrActionInfo('Prescription saved to history. You can still add medicines from this review.');
      if (ocrMedsAdded) {
        closeOcrReviewModal();
      }
    } catch (err) {
      alert(err.response?.data?.detail || 'Could not save this prescription record.');
    } finally {
      setRecordSaving(false);
    }
  };

  const openPrescriptionUpload = () => {
    if (requireProfileOrOpen()) return;

    if (!currentUser?.is_premium && savedPrescriptions.length >= FREE_TIER_PRESCRIPTION_LIMIT) {
      openPremiumUpsell('prescription_limit');
      return;
    }

    setPrescriptionModalOpen(true);
  };

  const openPrescriptionFile = async (recordId) => {
    if (!recordId) return;
    try {
      setFilePreviewLoading(true);
      const res = await axios.get(`${API_BASE}/me/prescriptions/${recordId}/file`, {
        ...getAuthConfig(),
        responseType: 'blob',
      });
      const blobUrl = URL.createObjectURL(res.data);
      if (filePreviewUrl) URL.revokeObjectURL(filePreviewUrl);
      setFilePreviewUrl(blobUrl);
      setFilePreviewMime(res.headers?.['content-type'] || res.data?.type || '');
      const record = savedPrescriptions.find((item) => item.id === recordId);
      setFilePreviewName(record?.uploaded_file_name || 'Uploaded file');
      setFilePreviewOpen(true);
    } catch (err) {
      alert(err.response?.data?.detail || 'Could not open uploaded file.');
    } finally {
      setFilePreviewLoading(false);
    }
  };

  const deletePrescriptionRecord = async (recordId) => {
    if (!recordId) return;
    try {
      setDeleteRecordLoading(true);
      await axios.delete(`${API_BASE}/me/prescriptions/${recordId}`, getAuthConfig());
      await fetchPrescriptions();
      await fetchMeds();
      scheduleSafetyRefresh();
      setPendingDeleteRecordId(null);
    } catch (err) {
      if (err.response?.status === 404) {
        setSavedPrescriptions((prev) => prev.filter((record) => record.id !== recordId));
        setPendingDeleteRecordId(null);
        await fetchMeds();
        scheduleSafetyRefresh();
        return;
      }
      alert(err.response?.data?.detail || 'Could not delete this record.');
    } finally {
      setDeleteRecordLoading(false);
    }
  };

  if (!authHydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-transparent">
        <GlassCard className="text-center py-8 px-10">
          <div className="w-10 h-10 mx-auto rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
          <p className="mt-4 text-sm text-slate-500">Restoring your session...</p>
        </GlassCard>
      </div>
    );
  }

  if (token && !currentUser && sessionRestorePending) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-transparent">
        <GlassCard className="text-center py-8 px-10">
          <div className="w-10 h-10 mx-auto rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
          <p className="mt-4 text-sm text-slate-500">Reconnecting your secure session...</p>
        </GlassCard>
      </div>
    );
  }

  if (token && !currentUser) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4 bg-transparent">
        <GlassCard className="text-center py-8 px-10">
          <div className="w-10 h-10 mx-auto rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
          <p className="mt-4 text-sm text-slate-500">Restoring your session...</p>
        </GlassCard>
      </div>
    );
  }

  if (!token || !currentUser) {
    return (
      <div className="min-h-screen overflow-y-auto flex items-start sm:items-center justify-center px-4 py-8 bg-transparent">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
            <GlassCard className="relative text-center py-6 sm:py-7">
              {googleAuthLoading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="absolute inset-0 z-20 flex items-center justify-center rounded-lg bg-white/85 backdrop-blur-[2px]"
                >
                  <div className="flex flex-col items-center gap-3 px-6">
                    <div className="h-10 w-10 rounded-full border-2 border-indigo-200 border-t-indigo-600 animate-spin" />
                    <div className="text-center">
                      <p className="text-sm font-semibold text-slate-900">Signing you in with Google</p>
                      <p className="text-xs text-slate-500 mt-1">Finishing secure session setup...</p>
                    </div>
                  </div>
                </motion.div>
              )}
            <img src={appLogo} alt="PolySafe logo" className="w-14 h-14 mx-auto mb-3 rounded-xl object-cover shadow-sm" />
            <h1 className="text-2xl font-bold text-slate-900 mb-1">PolySafe</h1>
            <p className="text-slate-500 mb-4 text-sm font-light italic">Secure Medication Safety Platform</p>

            <div className="grid grid-cols-2 gap-2 mb-5">
              <button
                onClick={() => switchAuthMode('login')}
                className={`rounded-lg py-2 text-sm font-semibold border transition-all ${authMode === 'login' ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'}`}
              >
                Login
              </button>
              <button
                onClick={() => switchAuthMode('register')}
                className={`rounded-lg py-2 text-sm font-semibold border transition-all ${authMode === 'register' ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'}`}
              >
                Sign Up
              </button>
            </div>

            {authError && <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-2 mb-3 text-left">{authError}</p>}
            {authInfo && <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-2 mb-3 text-left">{authInfo}</p>}

            {authMode === 'register' && (
              <div className="mb-3 text-left">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Full Name</label>
                <input
                  type="text"
                  placeholder="Enter your full name"
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 text-slate-900 outline-none"
                  value={authName}
                  onChange={(e) => setAuthName(sanitizePersonNameInput(e.target.value, 120))}
                />
              </div>
            )}

            {authMode === 'register' && (
              <div className="mb-3 text-left">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Role</label>
                <select
                  value={authRole}
                  onChange={(e) => setAuthRole(e.target.value)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 text-slate-900 outline-none"
                >
                  <option value="patient">Patient</option>
                  <option value="caregiver">Caregiver</option>
                </select>
              </div>
            )}

            <div className="mb-3 text-left">
              <label className="block text-xs font-semibold text-slate-600 mb-1">Email Address</label>
              <input
                type="email"
                placeholder="name@example.com"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 text-slate-900 outline-none"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
              />
            </div>

            {authMode !== 'forgot' && (
              <div className="mb-3 text-left">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Password</label>
                <div className="relative">
                  <input
                    type={showAuthPassword ? 'text' : 'password'}
                    placeholder="Enter password"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 pr-12 text-slate-900 outline-none"
                    value={authPassword}
                    onChange={(e) => setAuthPassword(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAuthSubmit()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowAuthPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer"
                    aria-label={showAuthPassword ? 'Hide password' : 'Show password'}
                  >
                    {showAuthPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-1">Minimum {minPasswordLength} characters.</p>
              </div>
            )}

            {authMode === 'register' && (
              <div className="mb-3 text-left">
                <label className="block text-xs font-semibold text-slate-600 mb-1">Confirm Password</label>
                <div className="relative">
                  <input
                    type={showAuthPassword ? 'text' : 'password'}
                    placeholder="Re-enter password"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 pr-12 text-slate-900 outline-none"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowAuthPassword((prev) => !prev)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer"
                    aria-label={showAuthPassword ? 'Hide passwords' : 'Show passwords'}
                  >
                    {showAuthPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-1">Use the same toggle to view both password fields.</p>
              </div>
            )}

            {(authMode !== 'forgot' || !forgotOtpSent) && (
              <button
                onClick={handleAuthSubmit}
                disabled={authLoading}
                className="mt-6 w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-4 rounded-xl transition-all disabled:opacity-60"
              >
                {authLoading ? 'Please wait...' : authMode === 'register' ? 'Create Account' : authMode === 'login' ? 'Sign In' : 'Send OTP'}
              </button>
            )}

            {authMode !== 'forgot' && (
              <div className="mt-3">
                {googleEnabled ? (
                  <>
                    <div ref={googleSlotRef} className={`flex justify-center ${googleAuthLoading ? 'opacity-40 pointer-events-none' : ''}`} />
                    {!googleButtonReady && !googleUiError && (
                      <p className="text-xs text-slate-500 text-left mt-1">Loading Google sign-in...</p>
                    )}
                    {googleUiError && (
                      <p className="text-xs text-red-600 text-left mt-1">
                        {googleUiError} Current origin: {window.location.origin}
                      </p>
                    )}
                  </>
                ) : (
                  <p className="text-xs text-slate-500 text-left">Google Sign-In is not configured. Set VITE_GOOGLE_CLIENT_ID in frontend env and GOOGLE_CLIENT_ID in backend env.</p>
                )}
              </div>
            )}

            {authMode === 'forgot' && (
              <>
                {!forgotOtpVerified && forgotOtpSent && (
                  <>
                    <div className="mt-3 text-left">
                      <label className="block text-xs font-semibold text-slate-600 mb-1">OTP Code</label>
                      <input
                        type="text"
                        placeholder="Enter 6-digit code"
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 text-slate-900 outline-none"
                        value={resetCode}
                        onChange={(e) => setResetCode(sanitizeNumericInput(e.target.value, { maxLength: 6, allowDecimal: false }))}
                      />
                    </div>
                    <button
                      onClick={handleVerifyOtp}
                      disabled={authLoading}
                      className="mt-3 w-full bg-slate-100 hover:bg-slate-200 text-slate-900 font-semibold py-3 rounded-xl border border-slate-200 transition-all disabled:opacity-60"
                    >
                      Verify OTP
                    </button>
                  </>
                )}

                {forgotOtpVerified && (
                  <>
                    <div className="mt-3 text-left">
                      <label className="block text-xs font-semibold text-slate-600 mb-1">New Password</label>
                      <div className="relative">
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          placeholder="Enter new password"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 pr-12 text-slate-900 outline-none"
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                        />
                        <button
                          type="button"
                          onClick={() => setShowNewPassword((prev) => !prev)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer"
                          aria-label={showNewPassword ? 'Hide new password' : 'Show new password'}
                        >
                          {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                      <p className="text-xs text-slate-500 mt-1">Minimum {minPasswordLength} characters.</p>
                    </div>

                    <div className="mt-3 text-left">
                      <label className="block text-xs font-semibold text-slate-600 mb-1">Confirm New Password</label>
                      <div className="relative">
                        <input
                          type={showNewPassword ? 'text' : 'password'}
                          placeholder="Re-enter new password"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-5 py-3 pr-12 text-slate-900 outline-none"
                          value={confirmNewPassword}
                          onChange={(e) => setConfirmNewPassword(e.target.value)}
                        />
                        <button
                          type="button"
                          onClick={() => setShowNewPassword((prev) => !prev)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 cursor-pointer"
                          aria-label={showNewPassword ? 'Hide confirm password' : 'Show confirm password'}
                        >
                          {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </div>
                    </div>

                    <button
                      onClick={handleResetPassword}
                      disabled={authLoading}
                      className="mt-3 w-full bg-indigo-700 hover:bg-indigo-600 text-white font-semibold py-3 rounded-xl transition-all disabled:opacity-60"
                    >
                      Reset Password
                    </button>
                  </>
                )}
              </>
            )}

            {authMode === 'login' && (
              <button
                onClick={() => switchAuthMode('forgot')}
                className="mt-4 text-indigo-500 hover:text-indigo-700 text-sm"
              >
                Forgot password?
              </button>
            )}

            {authMode === 'forgot' && (
              <button
                onClick={() => switchAuthMode('login')}
                className="mt-4 text-indigo-500 hover:text-indigo-700 text-sm"
              >
                Back to sign in
              </button>
            )}

            {authMode === 'register' && (
              <button
                onClick={() => switchAuthMode('login')}
                className="mt-4 text-indigo-500 hover:text-indigo-700 text-sm"
              >
                Already have an account? Sign in
              </button>
            )}
          </GlassCard>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#FBFBFD] text-slate-900 [&_button]:transition-all [&_button]:duration-200 [&_button]:ease-in-out">
      <AppSidebar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        currentUser={currentUser}
        activeView={activeView}
        onNavigate={(view) => {
          if ((view === 'history' || view === 'safety') && requireProfileOrOpen()) return;
          navigateToView(view);
        }}
        onRequestLogout={requestLogout}
        onOpenAccountSwitcher={() => setAccountSwitcherOpen(true)}
        medsLength={meds.length}
        profileRequired={profileRequired}
        profileNudgeVisible={profileNudgeVisible}
      />

      {/* Main Content */}
      <main className="flex-1 h-screen overflow-hidden">
        <div className="h-full p-4 overflow-hidden">
          {offlineInfo && (
            <div className="mb-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {offlineInfo}
            </div>
          )}
          {profileSwitching ? (
            <div className="h-full w-full max-w-5xl mx-auto space-y-4 animate-pulse">
              <div className="h-24 rounded-2xl bg-slate-200" />
              <div className="h-14 rounded-xl bg-slate-200" />
              <div className="h-14 rounded-xl bg-slate-200" />
              <div className="h-14 rounded-xl bg-slate-200" />
            </div>
          ) : (
          <AnimatePresence mode="wait">
          {activeView === 'dashboard' ? (
            <DashboardView
              GlassCard={GlassCard}
              entranceVariants={entranceVariants}
              meds={meds}
              savedPrescriptions={savedPrescriptions}
              interactions={interactions}
              profileRequired={profileRequired}
              onUploadPrescription={openPrescriptionUpload}
              openSafetyPage={openSafetyPage}
              medSearch={medSearch}
              setMedSearch={setMedSearch}
              filteredMeds={filteredMeds}
              getMedicationRiskTag={getMedicationRiskTag}
              openSafetyForInteraction={openSafetyForInteraction}
              renderHighlightedText={renderHighlightedText}
              formatMedicationSource={formatMedicationSource}
              openEditMed={openEditMed}
              deleteMed={deleteMed}
              manualError={manualError}
              manualDrugType={manualDrugType}
              setManualDrugType={setManualDrugType}
              manualDrugName={manualDrugName}
              setManualDrugName={(value) => setManualDrugName(sanitizeMedicationNameInput(value, 200))}
              handleManualAdd={handleManualAdd}
              manualDose={manualDose}
              setManualDose={(value) => setManualDose(sanitizeDoseInput(value, 100))}
              manualFrequency={manualFrequency}
              setManualFrequency={(value) => setManualFrequency(sanitizeFrequencyInput(value, 100))}
              manualSaving={manualSaving}
              uploadStage={uploadStage}
            />
          ) : activeView === 'history' ? (
            <HistoryView
              GlassCard={GlassCard}
              savedPrescriptions={savedPrescriptions}
              formatPrescriptionDate={formatPrescriptionDate}
              openPrescriptionFile={openPrescriptionFile}
              filePreviewLoading={filePreviewLoading}
              setPendingDeleteRecordId={setPendingDeleteRecordId}
              onUploadPrescription={openPrescriptionUpload}
            />
          ) : activeView === 'profile' ? (
            <ProfileView
              GlassCard={GlassCard}
              profileError={profileError}
              profileForm={profileForm}
              setProfileForm={setProfileForm}
              profileSaving={profileSaving}
              profileActionLoading={profileActionLoading}
              submitProfile={submitProfile}
              profiles={accountProfiles}
              activeProfileId={activeProfileId}
              onAddNewProfile={addNewProfile}
              onSwitchProfile={switchProfile}
              currentUser={currentUser}
              onRequirePremium={openPremiumUpsell}
              caregiverPatientLimit={FREE_TIER_CAREGIVER_PATIENT_LIMIT}
              deleteAccountText={deleteAccountText}
              setDeleteAccountText={setDeleteAccountText}
              deleteAccountLoading={deleteAccountLoading}
              deleteMyAccount={deleteMyAccount}
            />
          ) : activeView === 'upgrade' ? (
            <UpgradeView
              GlassCard={GlassCard}
              entranceVariants={entranceVariants}
              premiumPriceUsd={PREMIUM_PRICE_USD}
              onBack={() => navigateToView('dashboard')}
              currentUser={currentUser}
            />
          ) : (
            <div className="h-full overflow-y-auto pr-1">
              <SafetyAnalysisView
                meds={meds}
                interactions={interactions}
                report={safetyReport}
                currentUser={currentUser}
                profile={profileForm}
                setActiveView={(view) => navigateToView(view)}
                selectedInteraction={selectedSafetyInteraction}
              />
            </div>
          )}
        </AnimatePresence>
          )}
        </div>
      </main>

      <AppModals
        filePreviewOpen={filePreviewOpen}
        filePreviewUrl={filePreviewUrl}
        filePreviewName={filePreviewName}
        filePreviewMime={filePreviewMime}
        setFilePreviewUrl={setFilePreviewUrl}
        setFilePreviewOpen={setFilePreviewOpen}
        prescriptionModalOpen={prescriptionModalOpen}
        setPrescriptionModalOpen={setPrescriptionModalOpen}
        manualError={manualError}
        isDragOver={isDragOver}
        setIsDragOver={setIsDragOver}
        handleDropUpload={handleDropUpload}
        handleUpload={handleUpload}
        isUploading={isUploading}
        ocrResults={ocrResults}
        closeOcrReviewModal={closeOcrReviewModal}
        ocrActionInfo={ocrActionInfo}
        ocrReviewItems={ocrReviewItems}
        updateReviewedDrug={updateReviewedDrug}
        confirmDrug={confirmDrug}
        confirmAllReviewedDrugs={confirmAllReviewedDrugs}
        bulkAddLoading={bulkAddLoading}
        savePrescriptionRecord={savePrescriptionRecord}
        recordSaving={recordSaving}
        rawText={rawText}
        ocrRecordSaved={ocrRecordSaved}
        pendingEditMed={pendingEditMed}
        updateMedLoading={updateMedLoading}
        setPendingEditMed={setPendingEditMed}
        editMedName={editMedName}
        setEditMedName={(value) => setEditMedName(sanitizeMedicationNameInput(value, 200))}
        editMedType={editMedType}
        setEditMedType={setEditMedType}
        editMedDose={editMedDose}
        setEditMedDose={(value) => setEditMedDose(sanitizeDoseInput(value, 100))}
        editMedFrequency={editMedFrequency}
        setEditMedFrequency={(value) => setEditMedFrequency(sanitizeFrequencyInput(value, 100))}
        submitEditMed={submitEditMed}
        pendingDeleteRecordId={pendingDeleteRecordId}
        deleteRecordLoading={deleteRecordLoading}
        setPendingDeleteRecordId={setPendingDeleteRecordId}
        deletePrescriptionRecord={deletePrescriptionRecord}
        pendingDeleteMedId={pendingDeleteMedId}
        deleteMedLoading={deleteMedLoading}
        setPendingDeleteMedId={setPendingDeleteMedId}
        confirmDeleteMed={confirmDeleteMed}
        premiumModalOpen={premiumModalOpen}
        setPremiumModalOpen={setPremiumModalOpen}
        premiumContext={premiumContext}
        premiumPriceUsd={PREMIUM_PRICE_USD}
        onOpenUpgradePage={openUpgradePage}
      />

      <AnimatePresence>
        {accountSwitcherOpen && (
          <div className="fixed inset-0 z-1200 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => !switchingAccountEmail && setAccountSwitcherOpen(false)}
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              className="relative w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-xl p-5"
            >
              <h3 className="text-lg font-semibold text-slate-900">Switch account</h3>
              <p className="text-sm text-slate-600 mt-1">Choose a previously signed-in account.</p>

              <div className="mt-4 space-y-2 max-h-64 overflow-y-auto pr-1">
                {savedAccounts.length === 0 ? (
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
                    No saved accounts yet.
                  </div>
                ) : (
                  savedAccounts.map((account) => {
                    const accountEmail = String(account?.email || '').trim().toLowerCase();
                    const isCurrent = accountEmail === currentAccountEmail;
                    const isSwitching = switchingAccountEmail === accountEmail;

                    return (
                      <button
                        key={accountEmail}
                        type="button"
                        disabled={isCurrent || Boolean(switchingAccountEmail)}
                        onClick={() => switchSavedAccount(account)}
                        className={`w-full rounded-lg border px-3 py-2 text-left transition-all ${isCurrent ? 'border-indigo-200 bg-indigo-50' : 'border-slate-200 hover:bg-slate-50'} disabled:opacity-60`}
                      >
                        <p className="text-sm font-semibold text-slate-900">{account.profile_name || account.name || account.email}</p>
                        <p className="text-xs text-slate-500 mt-0.5">{account.email}</p>
                        {isCurrent && <p className="text-[11px] text-indigo-600 mt-1">Current account</p>}
                        {isSwitching && <p className="text-[11px] text-slate-500 mt-1">Switching...</p>}
                      </button>
                    );
                  })
                )}
              </div>

              <div className="mt-4 flex items-center justify-end gap-2">
                <button
                  onClick={() => setAccountSwitcherOpen(false)}
                  disabled={Boolean(switchingAccountEmail)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  Close
                </button>
                <button
                  onClick={async () => {
                    setAccountSwitcherOpen(false);
                    await executeLogout();
                    switchAuthMode('login');
                  }}
                  disabled={Boolean(switchingAccountEmail)}
                  className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  Add another account
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {logoutConfirmOpen && (
          <div className="fixed inset-0 z-1210 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setLogoutConfirmOpen(false)}
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              className="relative w-full max-w-sm bg-white border border-slate-200 rounded-2xl shadow-xl p-5"
            >
              <h3 className="text-lg font-semibold text-slate-900">Log out?</h3>
              <p className="text-sm text-slate-600 mt-1">You can sign back in anytime.</p>

              <div className="mt-5 flex items-center justify-end gap-2">
                <button
                  onClick={() => setLogoutConfirmOpen(false)}
                  className="px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmLogout}
                  className="px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-500"
                >
                  Log out
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {congratsModalOpen && (
          <div className="fixed inset-0 z-1210 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setCongratsModalOpen(false)}
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              className="relative w-full max-w-sm bg-white border-2 border-indigo-200 rounded-2xl shadow-2xl p-6 text-center"
            >
              <div className="mx-auto w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mb-4 shadow-inner">
                <span className="text-3xl">🎉</span>
              </div>
              <h3 className="text-2xl font-bold text-slate-900">Congratulations!</h3>
              <p className="text-sm text-slate-600 mt-2">Your PolySafe Premium subscription is active. All premium features are instantly unlocked!</p>

              <div className="mt-6 flex justify-center">
                <button
                  onClick={() => setCongratsModalOpen(false)}
                  className="w-full px-4 py-3 rounded-xl bg-indigo-600 text-white font-semibold hover:bg-indigo-500 shadow-md transition-colors"
                >
                  Start Using Premium
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {loggingOut && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-1220 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center"
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.98, opacity: 0 }}
              className="rounded-2xl border border-white/20 bg-white/10 px-7 py-6 text-center"
            >
              <div className="mx-auto h-10 w-10 rounded-full border-2 border-white/30 border-t-white animate-spin" />
              <p className="mt-3 text-white text-sm font-semibold">Signing you out...</p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default App;
