import React, { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, CheckCircle2, CreditCard, Lock, ShieldCheck } from 'lucide-react';

const PaymentView = ({ GlassCard, entranceVariants, premiumPriceUsd, onBack }) => {
  const [cardholder, setCardholder] = useState('');
  const [cardNumber, setCardNumber] = useState('');
  const [expiry, setExpiry] = useState('');
  const [cvv, setCvv] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [country, setCountry] = useState('United States');
  const [agree, setAgree] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');
  const [mockTransactionId, setMockTransactionId] = useState('');

  const sanitizedCardholder = cardholder.replace(/[^A-Za-z\s'-.]/g, '').replace(/\s{2,}/g, ' ').slice(0, 80);
  const sanitizedCardNumber = cardNumber.replace(/\D/g, '').slice(0, 16);
  const prettyCardNumber = sanitizedCardNumber.replace(/(\d{4})(?=\d)/g, '$1 ').trim();
  const sanitizedExpiry = expiry.replace(/[^0-9/]/g, '').slice(0, 5);
  const sanitizedCvv = cvv.replace(/\D/g, '').slice(0, 4);
  const sanitizedPostalCode = postalCode.replace(/[^A-Za-z0-9\s-]/g, '').slice(0, 12);

  const billingSummary = useMemo(() => ({
    monthly: premiumPriceUsd,
    tax: Number((premiumPriceUsd * 0.08).toFixed(2)),
    total: Number((premiumPriceUsd * 1.08).toFixed(2)),
  }), [premiumPriceUsd]);

  const validatePaymentForm = () => {
    const normalizedName = sanitizedCardholder.trim();
    if (normalizedName.length < 2) return 'Enter cardholder name.';
    if (sanitizedCardNumber.length !== 16) return 'Card number must be 16 digits.';
    if (!/^\d{2}\/\d{2}$/.test(sanitizedExpiry)) return 'Expiry must be in MM/YY format.';

    const [mmStr, yyStr] = sanitizedExpiry.split('/');
    const month = Number(mmStr);
    const year = Number(`20${yyStr}`);
    if (!Number.isInteger(month) || month < 1 || month > 12) return 'Expiry month is invalid.';

    const now = new Date();
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth() + 1;
    if (year < currentYear || (year === currentYear && month < currentMonth)) {
      return 'Card appears to be expired.';
    }

    if (sanitizedCvv.length < 3) return 'CVV must be at least 3 digits.';
    if (sanitizedPostalCode.trim().length < 3) return 'Postal code is too short.';
    if (!agree) return 'You must accept terms before continuing.';
    return '';
  };

  const simulatePayment = async () => {
    setStatus('idle');
    const validationError = validatePaymentForm();
    if (validationError) {
      setStatus('error');
      setMessage(validationError);
      return;
    }

    setSubmitting(true);
    setMessage('Submitting secure payment...');
    try {
      await new Promise((resolve) => setTimeout(resolve, 900));
      await new Promise((resolve) => setTimeout(resolve, 700));

      const mockId = `PS-${Date.now().toString().slice(-6)}-${Math.floor(Math.random() * 900 + 100)}`;
      setMockTransactionId(mockId);
      setStatus('success');
      setMessage('Payment simulation successful. Premium access can now be provisioned.');
    } catch {
      setStatus('error');
      setMessage('Could not simulate payment right now. Please retry.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <motion.div key="payment" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="h-full overflow-y-auto pr-1">
      <motion.div custom={0.08} variants={entranceVariants} initial="hidden" animate="show" className="w-full max-w-5xl mx-auto space-y-4">
        <GlassCard className="bg-linear-to-r from-emerald-50 via-white to-cyan-50 border border-emerald-100">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <p className="text-[11px] tracking-widest uppercase font-bold text-emerald-600">Checkout</p>
              <h2 className="text-2xl font-bold text-slate-900 mt-1">Premium Payment</h2>
              <p className="text-sm text-slate-600 mt-1">This is a simulation flow for presentation and UX testing.</p>
            </div>
            <button onClick={onBack} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <GlassCard className="lg:col-span-2 border border-slate-200">
            <h3 className="text-lg font-semibold text-slate-900">Card Details</h3>
            <p className="text-xs text-slate-500 mt-1">No real charge occurs. This page only simulates payment experience.</p>

            <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Cardholder Name</label>
                <input
                  value={cardholder}
                  onChange={(e) => setCardholder(e.target.value)}
                  placeholder="Full name on card"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-semibold text-slate-700 mb-1">Card Number</label>
                <div className="relative">
                  <CreditCard className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    value={prettyCardNumber}
                    onChange={(e) => setCardNumber(e.target.value)}
                    placeholder="1234 5678 9012 3456"
                    className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Expiry (MM/YY)</label>
                <input
                  value={sanitizedExpiry}
                  onChange={(e) => setExpiry(e.target.value)}
                  placeholder="08/29"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">CVV</label>
                <input
                  value={sanitizedCvv}
                  onChange={(e) => setCvv(e.target.value)}
                  placeholder="123"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Postal Code</label>
                <input
                  value={sanitizedPostalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                  placeholder="10001"
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Country</label>
                <select value={country} onChange={(e) => setCountry(e.target.value)} className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm">
                  <option>United States</option>
                  <option>United Kingdom</option>
                  <option>Canada</option>
                  <option>Australia</option>
                  <option>Pakistan</option>
                  <option>India</option>
                </select>
              </div>
            </div>

            <label className="mt-4 flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5" />
              <span className="text-sm text-slate-700">I agree to simulated billing terms for demo purposes.</span>
            </label>

            <button
              onClick={simulatePayment}
              disabled={submitting}
              className="mt-4 w-full sm:w-auto px-5 py-2.5 rounded-lg bg-emerald-600 text-white font-semibold hover:bg-emerald-500 disabled:opacity-60"
            >
              {submitting ? 'Processing...' : 'Simulate Secure Payment'}
            </button>

            {message && (
              <div className={`mt-4 rounded-lg border px-3 py-2 text-sm ${status === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : status === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>
                {message}
              </div>
            )}
          </GlassCard>

          <GlassCard className="border border-slate-200 h-fit">
            <h3 className="text-lg font-semibold text-slate-900">Order Summary</h3>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between text-slate-700"><span>Premium Plan</span><span>${billingSummary.monthly.toFixed(2)}</span></div>
              <div className="flex justify-between text-slate-700"><span>Estimated Tax</span><span>${billingSummary.tax.toFixed(2)}</span></div>
              <div className="border-t border-slate-200 pt-2 flex justify-between font-semibold text-slate-900"><span>Total</span><span>${billingSummary.total.toFixed(2)}</span></div>
            </div>

            <div className="mt-4 space-y-2 text-xs text-slate-600">
              <p className="inline-flex items-center gap-1"><Lock className="w-3.5 h-3.5 text-slate-500" /> Simulated PCI-like form checks</p>
              <p className="inline-flex items-center gap-1"><ShieldCheck className="w-3.5 h-3.5 text-slate-500" /> No real payment gateway connected</p>
              <p className="inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5 text-slate-500" /> Built for premium UX walkthrough</p>
            </div>

            {status === 'success' && (
              <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
                <p className="text-xs uppercase tracking-wide font-semibold text-emerald-700">Transaction</p>
                <p className="text-sm font-bold text-emerald-800 mt-1">{mockTransactionId}</p>
                <p className="text-xs text-emerald-700 mt-1">You can use this in demos as a mock receipt id.</p>
              </div>
            )}
          </GlassCard>
        </div>
      </motion.div>
    </motion.div>
  );
};

export default PaymentView;
