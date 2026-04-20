import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, CheckCircle2, CreditCard, Lock, ShieldCheck } from 'lucide-react';
import axios from 'axios';

const UpgradeView = ({ GlassCard, entranceVariants, premiumPriceUsd, onBack, currentUser }) => {
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  if (currentUser?.is_premium) {
    return (
      <div className="h-full flex items-center justify-center">
        <GlassCard className="text-center p-8 max-w-lg border-2 border-indigo-200">
          <div className="mx-auto w-16 h-16 bg-indigo-100 rounded-full flex items-center justify-center mb-4">
             <CheckCircle2 className="w-8 h-8 text-indigo-600" />
          </div>
          <h2 className="text-3xl font-bold text-slate-900 mb-2">You are Premium!</h2>
          <p className="text-slate-600 mb-8">Thank you for your subscription. All premium features, including unlimited medication tracking and priority OCR processing, are instantly unlocked across your account.</p>
          <button onClick={onBack} className="px-6 py-2.5 rounded-lg bg-indigo-600 text-white font-semibold shadow hover:bg-indigo-700 transition-colors">
            Return to Dashboard
          </button>
        </GlassCard>
      </div>
    );
  }

  const handleUpgradeClick = async () => {
    setSubmitting(true);
    setErrorMsg('');
    try {
      const token = localStorage.getItem('polysafe_token') || '';
      const headers = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await axios.post(
        'http://localhost:8000/api/payments/create-checkout',
        {},
        { withCredentials: true, headers }
      );
      if (res.data && res.data.url) {
        window.location.href = res.data.url;
      } else {
        throw new Error('No checkout URL received');
      }
    } catch (err) {
      console.error(err);
      setErrorMsg('Failed to launch secure checkout. Please try again later.');
      setSubmitting(false);
    }
  };

  return (
    <motion.div key="upgrade" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="h-full overflow-y-auto pr-1 flex items-center justify-center">
      <motion.div custom={0.08} variants={entranceVariants} initial="hidden" animate="show" className="w-full max-w-4xl mx-auto space-y-6 pb-10">
        
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold text-slate-900">Upgrade to PolySafe Premium</h2>
          <p className="text-slate-600 mt-2 text-lg">Unlock advanced safety features for you and your family.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-3xl mx-auto">
          {/* Free Tier Card */}
          <GlassCard className="border border-slate-200 opacity-80 flex flex-col pt-6 px-6 pb-8">
            <h3 className="text-xl font-semibold text-slate-900">Basic Plan</h3>
            <p className="text-sm text-slate-500 mt-1">For casual individuals.</p>
            <div className="mt-4 mb-6">
              <span className="text-4xl font-bold text-slate-900">$0</span>
              <span className="text-slate-500 font-medium"> / forever</span>
            </div>
            <ul className="space-y-3 mb-8 flex-1">
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-slate-400" /> Advanced safety checks</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-slate-400" /> Up to 6 active medicines</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-slate-400" /> Save 2 OCR scan history</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-slate-400" /> 1 User Profile</li>
            </ul>
            <button onClick={onBack} className="w-full py-2.5 rounded-xl border border-slate-300 text-slate-700 font-medium hover:bg-slate-50 transition-colors">
              Return to Dashboard
            </button>
          </GlassCard>

          {/* Premium Tier Card */}
          <GlassCard className="border-2 border-indigo-500 relative flex flex-col pt-6 px-6 pb-8 shadow-xl shadow-indigo-100">
            <div className="absolute top-0 right-0 transform translate-x-2 -translate-y-3">
              <span className="bg-indigo-500 text-white text-xs font-bold uppercase tracking-wider py-1 px-3 rounded-full shadow-md">
                Recommended
              </span>
            </div>
            <h3 className="text-xl font-semibold text-indigo-900">Premium</h3>
            <p className="text-sm text-indigo-600/80 mt-1">Unlimited safety & tracking.</p>
            <div className="mt-4 mb-6">
              <span className="text-4xl font-bold text-indigo-900">${premiumPriceUsd}</span>
              <span className="text-indigo-600/80 font-medium"> / month</span>
            </div>
            <ul className="space-y-3 mb-8 flex-1">
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-indigo-500" /> <span className="font-medium">Unlimited</span> medicines</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-indigo-500" /> <span className="font-medium">Unlimited</span> scan history</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-indigo-500" /> <span className="font-medium">Unlimited</span> family profiles</li>
              <li className="flex items-center gap-2 text-sm text-slate-700"><CheckCircle2 className="w-4 h-4 text-indigo-500" /> Priority algorithm support</li>
            </ul>
            <button
              onClick={handleUpgradeClick}
              disabled={submitting}
              className="w-full py-3 rounded-xl bg-indigo-600 text-white font-semibold shadow hover:bg-indigo-700 transition-colors disabled:opacity-70 flex justify-center items-center gap-2"
            >
              <ShieldCheck className="w-4 h-4" />
              {submitting ? 'Connecting...' : 'Upgrade Now'}
            </button>
            {errorMsg && (
              <p className="text-xs text-red-600 text-center mt-3 bg-red-50 p-2 rounded-lg border border-red-100">{errorMsg}</p>
            )}
          </GlassCard>
        </div>
        
        <div className="text-center mt-6 flex justify-center items-center gap-2 text-slate-400 text-xs">
           <Lock className="w-3 h-3" /> Secure checkout provided by Stripe
        </div>
      </motion.div>
    </motion.div>
  );
};

export default UpgradeView;
