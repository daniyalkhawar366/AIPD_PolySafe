import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Shield,
  Upload,
  Trash2,
  CheckCircle,
  AlertTriangle,
  Plus,
  User,
  Activity,
  ChevronRight,
  Search,
  Check
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const GlassCard = ({ children, className = "" }) => (
  <div className={`bg-white/10 backdrop-blur-xl border border-white/20 rounded-2xl shadow-2xl p-6 ${className}`}>
    {children}
  </div>
);
const API_BASE = "http://localhost:8000/api";

const App = () => {
  const [userName, setUserName] = useState('');
  const [userId, setUserId] = useState('');
  const [meds, setMeds] = useState([]);
  const [interactions, setInteractions] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [ocrResults, setOcrResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const [activeView, setActiveView] = useState('dashboard');
  const [expandedInter, setExpandedInter] = useState(null);

  const fetchMeds = async () => {
    if (!userId) return;
    const res = await axios.get(`${API_BASE}/meds/${userId}`);
    setMeds(res.data);
  };

  const handleSetUser = () => {
    if (userName.trim()) setUserId(userName.trim());
  };

  useEffect(() => {
    if (userId) fetchMeds();
  }, [userId]);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !userId) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post(`${API_BASE}/upload?user_id=${userId}`, formData);
      setOcrResults(res.data.drugs);
    } catch (err) {
      alert("Upload failed. Check backend.");
    } finally {
      setIsUploading(false);
    }
  };

  const confirmDrug = async (drug) => {
    await axios.post(`${API_BASE}/add`, {
      user_id: userId,
      drug_name: drug.name,
      rxcui: drug.rxcui
    });
    setOcrResults(prev => prev.filter(d => d.name !== drug.name));
    fetchMeds();
  };

  const deleteMed = async (id) => {
    await axios.delete(`${API_BASE}/meds/${id}`);
    fetchMeds();
  };

  const checkSafety = async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API_BASE}/interactions/${userId}`);
      setInteractions(res.data.interactions);
      if (res.data.interactions.length > 0) setActiveView('safety');
    } finally {
      setLoading(false);
    }
  };


  if (!userId) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
        >
          <GlassCard className="text-center">
            <Shield className="w-16 h-16 text-indigo-400 mx-auto mb-6" />
            <h1 className="text-3xl font-bold text-white mb-2">PolySafe</h1>
            <p className="text-indigo-200/60 mb-8 font-light italic">Your Personalized Drug Safety Shield</p>
            <div className="relative group">
              <input
                type="text"
                placeholder="Enter Patient ID/Name"
                className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-4 text-white outline-none focus:ring-2 focus:ring-indigo-500 transition-all text-center placeholder:text-gray-500"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSetUser()}
              />
              <button
                onClick={handleSetUser}
                className="mt-6 w-full bg-indigo-600 hover:bg-indigo-500 text-white font-semibold py-4 rounded-xl transition-all shadow-[0_0_20px_rgba(79,70,229,0.3)]"
              >
                Access Dashboard
              </button>
            </div>
          </GlassCard>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen grid grid-cols-[280px_1fr] p-6 gap-6 max-w-7xl mx-auto">
      {/* Sidebar - Navigation & Stats */}
      <aside className="space-y-6">
        <GlassCard className="!p-4">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 rounded-full bg-indigo-600 flex items-center justify-center text-white font-bold">
              {userId[0].toUpperCase()}
            </div>
            <div>
              <p className="text-gray-400 text-xs">Patient Profile</p>
              <h3 className="text-white font-semibold truncate max-w-[150px]">{userId}</h3>
            </div>
          </div>
          <div className="space-y-4">
            <div className="bg-white/5 p-3 rounded-lg border border-white/5">
              <div className="flex justify-between items-center text-xs text-indigo-300 mb-1">
                <span>Active Meds</span>
                <Activity className="w-3 h-3" />
              </div>
              <span className="text-2xl font-bold text-white">{meds.length}</span>
            </div>
            
            {interactions.length > 0 && (
               <div className="bg-red-500/10 p-3 rounded-lg border border-red-500/20">
                <div className="flex justify-between items-center text-xs text-red-400 mb-1">
                  <span>Risk Alerts</span>
                  <AlertTriangle className="w-3 h-3" />
                </div>
                <span className="text-2xl font-bold text-red-500">{interactions.length}</span>
              </div>
            )}
          </div>
          <button
            onClick={() => { setUserId(''); setInteractions([]); setActiveView('dashboard'); }}
            className="mt-6 w-full text-xs text-red-400 hover:text-red-300 py-2 border border-red-900/10 rounded-lg transition-colors"
          >
            Logout session
          </button>
        </GlassCard>

        <nav className="space-y-2">
          <button 
            onClick={() => setActiveView('dashboard')}
            className={`w-full flex items-center justify-between p-4 rounded-xl transition-all ${activeView === 'dashboard' ? 'bg-indigo-600/20 border-indigo-500/40 text-white' : 'text-gray-500 hover:bg-white/5 border-transparent border'}`}
          >
            <span className="flex items-center gap-3"><Activity className="w-4 h-4" /> Dashboard</span>
            {activeView === 'dashboard' && <ChevronRight className="w-4 h-4" />}
          </button>
          
          <button 
            onClick={() => meds.length >= 2 && setActiveView('safety')}
            disabled={meds.length < 2}
            className={`w-full flex items-center justify-between p-4 rounded-xl transition-all ${activeView === 'safety' ? 'bg-indigo-600/20 border-indigo-500/40 text-white' : 'text-gray-500 hover:bg-white/5 border-transparent border disabled:opacity-30'}`}
          >
            <span className="flex items-center gap-3"><Shield className="w-4 h-4" /> Safety Analysis</span>
            {activeView === 'safety' && <ChevronRight className="w-4 h-4" />}
          </button>
        </nav>
      </aside>

      {/* Main Panel */}
      <main className="space-y-6 min-h-0 overflow-y-auto pr-2">
        <AnimatePresence mode="wait">
          {activeView === 'dashboard' ? (
            <motion.div
              key="dashboard"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="space-y-6"
            >
              <section className="grid grid-cols-2 gap-6">
                {/* Upload Section */}
                <GlassCard className="relative overflow-hidden group">
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <h2 className="text-xl font-bold text-white">Digital Vision</h2>
                      <p className="text-gray-400 text-sm">Upload Prescription or Report</p>
                    </div>
                    <Upload className="text-indigo-400 w-6 h-6" />
                  </div>

                  <label className="block border-2 border-dashed border-white/10 rounded-xl p-8 text-center cursor-pointer hover:border-indigo-500/50 hover:bg-indigo-500/5 transition-all">
                    <input type="file" className="hidden" onChange={handleUpload} accept="image/*,.pdf" />
                    {isUploading ? (
                      <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="w-8 h-8 border-2 border-indigo-400 border-t-transparent rounded-full mx-auto" />
                    ) : (
                      <div className="space-y-2">
                        <Plus className="w-10 h-10 text-gray-400 mx-auto" />
                        <span className="text-gray-500 text-sm">Analyze Document</span>
                      </div>
                    )}
                  </label>
                </GlassCard>

                {/* Active Medications List */}
                <GlassCard className="flex flex-col">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="text-xl font-bold text-white">Active Profile</h2>
                    <Search className="text-gray-500 w-5 h-5 cursor-pointer hover:text-indigo-400 transition-colors" />
                  </div>
                  <div className="space-y-3 flex-1 overflow-y-auto max-h-[220px] pr-2 scrollbar-thin scrollbar-thumb-white/10">
                    {meds.length === 0 ? (
                      <p className="text-gray-500 text-center py-8 italic text-sm">No medications tracked yet</p>
                    ) : (
                      meds.map(med => (
                        <motion.div
                          layout
                          key={med.id}
                          className="group flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5 hover:border-indigo-500/30 transition-all"
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
                            <div>
                              <p className="text-white text-sm font-medium">{med.name}</p>
                              <p className="text-gray-500 text-[10px]">RxCUI: {med.rxcui}</p>
                            </div>
                          </div>
                          <button onClick={() => deleteMed(med.id)} className="opacity-0 group-hover:opacity-100 p-2 text-red-500/60 hover:text-red-400 transition-all">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </motion.div>
                      ))
                    )}
                  </div>
                  {meds.length >= 2 && (
                    <button
                      onClick={checkSafety}
                      disabled={loading}
                      className="mt-6 w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-[0_0_15px_rgba(79,70,229,0.2)]"
                    >
                      {loading ? <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity }} className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full" /> : <><Shield className="w-4 h-4" /> Run Cross-Check</>}
                    </button>
                  )}
                </GlassCard>
              </section>
            </motion.div>
          ) : (
            <motion.div
              key="safety"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="space-y-6"
            >
              <div className="flex justify-between items-center mb-8 bg-indigo-500/5 p-6 rounded-3xl border border-indigo-500/10">
                <div>
                  <h2 className="text-2xl font-bold text-white">Safety Analysis Report</h2>
                  <p className="text-indigo-300/60 text-sm">Clinical Cross-Reference Results</p>
                </div>
                <button onClick={() => setActiveView('dashboard')} className="text-sm bg-white/5 hover:bg-white/10 text-white px-4 py-2 rounded-xl border border-white/5 transition-all">
                  Return to Dashboard
                </button>
              </div>

              <div className="space-y-4">
                {interactions.length === 0 ? (
                  <GlassCard className="text-center py-20">
                    <CheckCircle className="w-16 h-16 text-green-500 mx-auto mb-4 opacity-50" />
                    <p className="text-white text-xl font-bold">No High-Risk Interactions Found</p>
                    <p className="text-gray-500 mt-2">Your current profile appears stable according to clinical FDA data.</p>
                  </GlassCard>
                ) : (
                  interactions.map((inter, i) => (
                    <GlassCard 
                      key={i} 
                      className={`cursor-pointer transition-all hover:bg-white/[0.07] !border-l-4 ${inter.severity === 'High' ? '!border-l-red-500' : '!border-l-orange-400'}`}
                    >
                      <div onClick={() => setExpandedInter(expandedInter === i ? null : i)}>
                        <div className="flex items-start justify-between">
                          <div className="flex items-start gap-4">
                             <div className={`p-3 rounded-2xl ${inter.severity === 'High' ? 'bg-red-500/10 text-red-400' : 'bg-orange-500/10 text-orange-400'}`}>
                              <AlertTriangle className="w-6 h-6" />
                            </div>
                            <div className="space-y-1">
                              <h4 className="text-xl font-bold text-white">{inter.drug_a} + {inter.drug_b}</h4>
                              <span className={`inline-block text-[10px] uppercase font-black px-3 py-1 rounded-full ${inter.severity === 'High' ? 'bg-red-500 text-white' : 'bg-orange-500 text-white'}`}>
                                {inter.severity} Risk
                              </span>
                            </div>
                          </div>
                          <ChevronRight className={`w-5 h-5 text-gray-600 transition-transform ${expandedInter === i ? 'rotate-90' : ''}`} />
                        </div>

                        <AnimatePresence>
                          {expandedInter === i && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              className="overflow-hidden"
                            >
                              <div className="mt-6 pt-6 border-t border-white/5 space-y-4">
                                <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                                  <p className="text-xs text-indigo-400 font-bold uppercase mb-2">Primary Risk Summary</p>
                                  <p className="text-white text-lg font-medium leading-snug">{inter.summary}</p>
                                </div>
                                <div className="p-4">
                                  <p className="text-[10px] text-gray-500 font-bold uppercase mb-2">Clinical Source Evidence</p>
                                  <p className="text-gray-400 text-sm leading-relaxed italic border-l-2 border-white/10 pl-4">
                                    {inter.detail}
                                  </p>
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </GlassCard>
                  ))
                )}
              </div>

              {interactions.length > 0 && (
                <div className="bg-indigo-900/10 border border-indigo-400/20 p-6 rounded-3xl text-center">
                  <p className="text-indigo-300 text-xs italic flex items-center justify-center gap-3">
                    <Shield className="w-4 h-4" /> Data sourced from OpenFDA & RxNorm. Consult a pharmacist for confirmation.
                  </p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* OCR Results Modal - Root Level Pop-up */}
      <AnimatePresence>
        {ocrResults && (
          <div className="fixed inset-0 flex items-center justify-center p-4 z-999">
            {/* Backdrop Overlay */}
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOcrResults(null)}
              className="absolute inset-0 bg-black/70 backdrop-blur-md"
            />

            {/* Modal Box */}
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative bg-[#0f172a] border border-white/10 rounded-[32px] shadow-2xl p-8 w-full max-w-lg overflow-hidden"
            >
              <div className="absolute inset-0 bg-linear-to-br from-indigo-500/10 to-transparent pointer-events-none" />
              
              <div className="flex justify-between items-center mb-8 relative z-10">
                <div>
                  <h2 className="text-3xl font-bold text-white tracking-tight">Verify Results</h2>
                  <p className="text-indigo-300/60 text-sm mt-1">Detected {ocrResults.length} medications matching FDA data</p>
                </div>
                <button 
                  onClick={() => setOcrResults(null)} 
                  className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-white hover:bg-white/10 rounded-full transition-all"
                >
                  <span className="text-2xl">&times;</span>
                </button>
              </div>

              <div className="max-h-[380px] overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-white/10 relative z-10">
                {ocrResults.length === 0 ? (
                  <div className="text-center py-16">
                    <Shield className="w-12 h-12 text-gray-600 mx-auto mb-4 opacity-50" />
                    <p className="text-gray-500 italic">No clinical matches identified.</p>
                  </div>
                ) : (
                  ocrResults.map(drug => (
                    <div key={drug.name} className="group flex items-center justify-between p-4 bg-white/5 rounded-2xl border border-white/5 hover:border-indigo-500/30 transition-all">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center group-hover:bg-indigo-500/20 transition-colors">
                          <CheckCircle className="w-6 h-6 text-indigo-400" />
                        </div>
                        <div>
                          <p className="text-white font-bold text-lg">{drug.name}</p>
                          <p className="text-gray-500 text-xs uppercase tracking-tighter">Clinical Match Found</p>
                        </div>
                      </div>
                      <button 
                        onClick={() => confirmDrug(drug)} 
                        className="bg-indigo-600 hover:bg-indigo-500 text-white p-3 rounded-xl font-bold transition-all shadow-lg active:scale-95"
                      >
                        <Plus className="w-5 h-5" />
                      </button>
                    </div>
                  ))
                )}
              </div>

              {ocrResults.length > 0 && (
                <div className="mt-8 relative z-10 border-t border-white/5 pt-6 flex flex-col items-center">
                  <p className="text-gray-500 text-[10px] uppercase tracking-widest mb-6 px-4 py-1 bg-white/5 rounded-full">
                    Double check with your physical prescription
                  </p>
                  <button 
                    onClick={() => setOcrResults(null)}
                    className="w-full py-4 bg-white/5 hover:bg-white/10 text-white rounded-2xl font-bold transition-all border border-white/5 hover:border-white/10"
                  >
                    Done Verifying
                  </button>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default App;
