import React, { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle, AlertTriangle, ChevronDown, Shield, Activity, Pill, Download } from 'lucide-react';

const SEVERITY_CONFIG = {
  High: {
    dot: '#DC2626',
    badge: { bg: '#FEF2F2', text: '#991B1B', border: '#FECACA' },
    bar: '#DC2626',
    label: 'High Risk',
  },
  Medium: {
    dot: '#D97706',
    badge: { bg: '#FFFBEB', text: '#92400E', border: '#FDE68A' },
    bar: '#F59E0B',
    label: 'Medium Risk',
  },
  Low: {
    dot: '#059669',
    badge: { bg: '#ECFDF5', text: '#065F46', border: '#A7F3D0' },
    bar: '#059669',
    label: 'Low Risk',
  },
};

const FRIENDLY_TERM_MAP = [
  [/contraindicated/gi, 'not safe together'],
  [/concomitant use/gi, 'using these together'],
  [/hepatotoxic/gi, 'liver-harm'],
  [/toxicity/gi, 'harm'],
  [/hypotensive/gi, 'low blood pressure'],
  [/symptomatic/gi, 'noticeable'],
  [/initiation/gi, 'the first few days of use'],
  [/peripheral resistance/gi, 'blood vessel pressure'],
  [/cardiac output/gi, 'heart pumping strength'],
  [/clinical/gi, 'medical'],
  [/anticoagulation/gi, 'blood thinning'],
  [/major bleeding risk/gi, 'serious bleeding risk'],
  [/INR/gi, 'blood-thinning level (INR)'],
];

function toFriendlyText(text) {
  let result = String(text || '');
  FRIENDLY_TERM_MAP.forEach(([pattern, replacement]) => {
    result = result.replace(pattern, replacement);
  });
  return result;
}

function Badge({ severity }) {
  const cfg = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.Low;
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        padding: '3px 10px',
        borderRadius: 4,
        background: cfg.badge.bg,
        color: cfg.badge.text,
        border: `1px solid ${cfg.badge.border}`,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
      {cfg.label}
    </span>
  );
}

function StatCard({ label, value, accent }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #E5E7EB',
        borderRadius: 8,
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: '#9CA3AF',
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontSize: 28,
          fontWeight: 700,
          lineHeight: 1,
          color: accent || '#111827',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {value}
      </span>
    </div>
  );
}

const InteractionRow = forwardRef(function InteractionRow({ inter, index, isExpanded, onToggle, isSelected }, ref) {
  const cfg = SEVERITY_CONFIG[inter.severity] || SEVERITY_CONFIG.Low;
  const title = inter.kind === 'overdose' ? inter.drug_a : `${inter.drug_a} + ${inter.drug_b}`;
  const friendlySummary = toFriendlyText(inter.summary);
  const friendlyDetail = toFriendlyText(inter.detail);

  return (
    <div
      ref={ref}
      style={{
        background: '#fff',
        border: '1px solid #E5E7EB',
        boxShadow: isSelected ? '0 0 0 2px rgba(99, 102, 241, 0.18)' : 'none',
        borderLeft: `3px solid ${cfg.bar}`,
        borderRadius: '0 8px 8px 0',
        overflow: 'hidden',
      }}
    >
      {/* Header row */}
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 20px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 0 }}>
          <span
            style={{
              width: 32,
              height: 32,
              borderRadius: 6,
              background: inter.severity === 'High' ? '#FEF2F2' : '#FFFBEB',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <AlertTriangle
              size={15}
              style={{ color: inter.severity === 'High' ? '#DC2626' : '#D97706' }}
            />
          </span>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
            <span
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: '#111827',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              {title}
            </span>
            <span style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.4 }}>
              {friendlySummary}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
          <Badge severity={inter.severity} />
          <ChevronDown
            size={16}
            style={{
              color: '#9CA3AF',
              transition: 'transform 0.2s',
              transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            }}
          />
        </div>
      </button>

      {/* Expanded detail */}
      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            key="detail"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            <div
              style={{
                borderTop: '1px solid #F3F4F6',
                padding: '16px 20px 20px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              {/* Evidence */}
              <div
                style={{
                  background: '#F9FAFB',
                  border: '1px solid #E5E7EB',
                  borderRadius: 6,
                  padding: '12px 14px',
                }}
              >
                <p
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    letterSpacing: '0.07em',
                    textTransform: 'uppercase',
                    color: '#9CA3AF',
                    marginBottom: 6,
                  }}
                >
                  Why this matters
                </p>
                <p style={{ fontSize: 13.5, color: '#374151', lineHeight: 1.6, margin: 0 }}>
                  {friendlyDetail}
                </p>
              </div>

              {/* Guidance */}
              <div
                style={{
                  background: '#FFFBEB',
                  border: '1px solid #FDE68A',
                  borderRadius: 6,
                  padding: '12px 14px',
                  display: 'flex',
                  gap: 10,
                  alignItems: 'flex-start',
                }}
              >
                <Shield
                  size={14}
                  style={{ color: '#B45309', flexShrink: 0, marginTop: 2 }}
                />
                <div>
                  <p
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      letterSpacing: '0.07em',
                      textTransform: 'uppercase',
                      color: '#B45309',
                      marginBottom: 4,
                    }}
                  >
                    What you should do
                  </p>
                  <p style={{ fontSize: 13, color: '#78350F', lineHeight: 1.55, margin: 0 }}>
                    Do not adjust or stop any medication on your own. Share this report with your pharmacist or prescribing doctor before making any changes.
                  </p>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

export default function SafetyAnalysisView({
  meds = [],
  interactions = [],
  report = null,
  currentUser = null,
  profile = null,
  setActiveView = () => {},
  selectedInteraction = null,
}) {
  const [expandedInter, setExpandedInter] = useState(null);
  const rowRefs = useRef([]);

  const selectedInteractionKey = useMemo(() => {
    if (!selectedInteraction) return '';
    return [
      selectedInteraction.kind || '',
      selectedInteraction.severity || '',
      selectedInteraction.drug_a || '',
      selectedInteraction.drug_b || '',
      selectedInteraction.summary || '',
    ].join('|').toLowerCase();
  }, [selectedInteraction]);

  const severityCounts = report?.severity_counts || {
    High: interactions.filter((i) => i.severity === 'High').length,
    Medium: interactions.filter((i) => i.severity === 'Medium').length,
    Low: interactions.filter((i) => i.severity === 'Low').length,
  };
  const highCount = severityCounts.High || 0;
  const medCount = severityCounts.Medium || 0;
  const lowCount = severityCounts.Low || 0;

  const recommendations = Array.isArray(report?.recommendations) ? report.recommendations : [];
  const topPriority = Array.isArray(report?.top_priority_alerts) ? report.top_priority_alerts : [];
  const kindCounts = report?.kind_counts || {};

  const sorted = [...interactions].sort((a, b) => {
    const order = { High: 0, Medium: 1, Low: 2 };
    return (order[a.severity] ?? 9) - (order[b.severity] ?? 9);
  });

  const handleExportDoctorSummary = async () => {
    const now = new Date();
    const stamp = now.toISOString().slice(0, 10);
    const patientName = String(profile?.patient_name || currentUser?.name || 'Patient').trim() || 'Patient';
    const patientEmail = String(currentUser?.email || '').trim();
    const patientAge = profile?.age ? String(profile.age) : '';
    const chronicConditions = String(profile?.chronic_conditions_text || '').trim();
    const allergies = String(profile?.allergies_text || '').trim();

    const safePatientSlug = patientName
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '_')
      .replace(/^_+|_+$/g, '') || 'patient';

    const { jsPDF } = await import('jspdf');
    const doc = new jsPDF({ unit: 'pt', format: 'a4' });
    const margin = 40;
    const pageHeight = doc.internal.pageSize.getHeight();
    const pageWidth = doc.internal.pageSize.getWidth();
    const maxWidth = pageWidth - (margin * 2);
    let y = margin;

    const ensureSpace = (needed) => {
      if (y + needed > pageHeight - margin) {
        doc.addPage();
        y = margin;
      }
    };

    const writeLine = (text, { size = 11, bold = false, color = '#111827', gap = 6 } = {}) => {
      doc.setFont('helvetica', bold ? 'bold' : 'normal');
      doc.setFontSize(size);
      doc.setTextColor(color);
      const lines = doc.splitTextToSize(String(text || ''), maxWidth);
      ensureSpace(lines.length * (size + 3) + gap);
      doc.text(lines, margin, y);
      y += lines.length * (size + 3) + gap;
    };

    const writeSection = (title) => {
      y += 4;
      writeLine(title, { size: 14, bold: true, color: '#1f2937', gap: 8 });
    };

    doc.setFillColor(67, 56, 202);
    doc.rect(0, 0, pageWidth, 84, 'F');
    doc.setTextColor('#ffffff');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(20);
    doc.text('PolySafe Safety Report', margin, 36);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(11);
    doc.text(`Generated ${stamp}`, margin, 56);
    y = 104;

    doc.setFillColor(238, 242, 255);
    doc.roundedRect(margin, y - 8, maxWidth, 72, 8, 8, 'F');
    writeLine(`Patient: ${patientName}`, { size: 12, bold: true, color: '#312e81', gap: 3 });
    if (patientEmail) writeLine(`Email: ${patientEmail}`, { size: 10, color: '#4338ca', gap: 3 });
    if (patientAge) writeLine(`Age: ${patientAge}`, { size: 10, color: '#4338ca', gap: 3 });
    writeLine(`Chronic conditions: ${chronicConditions || 'Not provided'}`, { size: 10, color: '#4338ca', gap: 3 });
    writeLine(`Allergies: ${allergies || 'Not provided'}`, { size: 10, color: '#4338ca', gap: 10 });

    writeLine(
      `Tracked medications: ${meds.length}   |   Total safety flags: ${sorted.length}   |   High risk: ${highCount}   |   Medium risk: ${medCount}   |   Low risk: ${lowCount}`,
      { size: 11, gap: 12 },
    );

    writeSection('How the analysis works');
    writeLine('PolySafe compares the medication list against interaction data, then adds rule-based safety checks for duplicate ingredients, dose limits, schedule overlap, allergies, kidney/liver context, and food/alcohol risks.', { size: 11, gap: 4 });
    writeLine(`Risk breakdown: ${Object.entries(kindCounts).map(([key, value]) => `${key}: ${value}`).join(' | ') || 'No risk categories found'}`, { size: 11, gap: 8 });

    writeSection('Current medications');
    if (meds.length === 0) {
      writeLine('None', { size: 11 });
    } else {
      meds.forEach((med, idx) => {
        const dose = med?.dose ? `, dose: ${med.dose}` : '';
        const frequency = med?.frequency ? `, frequency: ${med.frequency}` : '';
        writeLine(`${idx + 1}. ${med?.name || 'Unknown'}${dose}${frequency}`, { size: 11, gap: 4 });
      });
    }

    writeSection('Top priority alerts');
    if (topPriority.length === 0) {
      writeLine('None', { size: 11 });
    } else {
      topPriority.forEach((alert, idx) => {
        writeLine(`${idx + 1}. [${alert?.severity || 'Unknown'}] ${toFriendlyText(alert?.summary || '')}`, { size: 11, gap: 4 });
      });
    }

    writeSection('Recommendations');
    if (recommendations.length === 0) {
      writeLine('None', { size: 11 });
    } else {
      recommendations.forEach((item, idx) => {
        writeLine(`${idx + 1}. ${toFriendlyText(item)}`, { size: 11, gap: 4 });
      });
    }

    writeSection('Detailed interaction list');
    if (sorted.length === 0) {
      writeLine('No interactions detected.', { size: 11 });
    } else {
      sorted.forEach((inter, idx) => {
        writeLine(`${idx + 1}. ${inter?.drug_a || 'Unknown'} + ${inter?.drug_b || 'Unknown'}`, { size: 11, bold: true, gap: 2 });
        writeLine(`Severity: ${inter?.severity || 'Unknown'}`, { size: 10, color: '#6b7280', gap: 2 });
        writeLine(`Summary: ${toFriendlyText(inter?.summary || '')}`, { size: 10, gap: 2 });
        writeLine(`Detail: ${toFriendlyText(inter?.detail || '')}`, { size: 10, gap: 6 });
      });
    }

    writeLine('Disclaimer: This summary is informational and does not replace medical advice.', { size: 10, color: '#6b7280', gap: 0 });
    doc.save(`${safePatientSlug}_safety_report_${stamp}.pdf`);
  };

  useEffect(() => {
    if (!selectedInteractionKey || sorted.length === 0) return;

    const selectedIndex = sorted.findIndex((inter) => {
      const key = [
        inter.kind || '',
        inter.severity || '',
        inter.drug_a || '',
        inter.drug_b || '',
        inter.summary || '',
      ].join('|').toLowerCase();
      return key === selectedInteractionKey;
    });

    if (selectedIndex === -1) return;

    setExpandedInter(selectedIndex);
    window.requestAnimationFrame(() => {
      rowRefs.current[selectedIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }, [selectedInteractionKey, sorted]);

  return (
    <div
      style={{
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif',
        color: '#111827',
        width: '100%',
        maxWidth: 'none',
        margin: 0,
        padding: '14px 10px 20px',
        boxSizing: 'border-box',
        height: '100%',
        minHeight: '100%',
        overflowY: 'auto',
      }}
    >
      {/* ── Page header ──────────────────────────────────────── */}
      <div style={{ marginBottom: 32 }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 12,
          }}
        >
          <div>
            <p
              style={{
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#6366F1',
                marginBottom: 6,
              }}
            >
              Clinical report
            </p>
            <h1 style={{ fontSize: 26, fontWeight: 700, lineHeight: 1.2, margin: 0 }}>
              Safety analysis
            </h1>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <button
              onClick={handleExportDoctorSummary}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                border: '1px solid #C7D2FE',
                color: '#4338CA',
                background: '#EEF2FF',
                padding: '8px 12px',
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 700,
                cursor: 'pointer',
              }}
              title="Download a doctor-ready summary"
            >
              <Download size={14} />
              Export
            </button>
          </div>
        </div>

        <hr style={{ border: 'none', borderTop: '1px solid #E5E7EB', marginTop: 20 }} />
      </div>

      {/* ── Stat strip ───────────────────────────────────────── */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: 10,
          marginBottom: 32,
        }}
      >
        <StatCard label="Tracked medications" value={meds.length} />
        <StatCard label="High risk" value={highCount} accent={highCount > 0 ? '#DC2626' : undefined} />
        <StatCard label="Medium risk" value={medCount} accent={medCount > 0 ? '#D97706' : undefined} />
        <StatCard label="Low risk" value={lowCount} accent={lowCount > 0 ? '#059669' : undefined} />
        <StatCard label="Total flags" value={interactions.length} />
      </div>

      {topPriority.length > 0 && (
        <div
          style={{
            background: '#FEF2F2',
            border: '1px solid #FECACA',
            borderRadius: 8,
            padding: '12px 14px',
            marginBottom: 14,
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: '#B91C1C',
            }}
          >
            Top priority now
          </p>
          <p style={{ margin: '6px 0 0', fontSize: 13.5, color: '#7F1D1D', lineHeight: 1.45 }}>
            {toFriendlyText(topPriority[0]?.summary || 'High-priority concern detected. Please review urgently.')}
          </p>
        </div>
      )}

      {recommendations.length > 0 && (
        <div
          style={{
            background: '#F9FAFB',
            border: '1px solid #E5E7EB',
            borderRadius: 8,
            padding: '12px 14px',
            marginBottom: 18,
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: '#6B7280',
            }}
          >
            Recommended next steps
          </p>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {recommendations.map((item, idx) => (
              <div key={`${item}-${idx}`} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                <Pill size={14} style={{ color: '#6366F1', flexShrink: 0, marginTop: 2 }} />
                <p style={{ margin: 0, fontSize: 13.5, color: '#374151', lineHeight: 1.45 }}>
                  {toFriendlyText(item)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div
        style={{
          background: '#F8FAFC',
          border: '1px solid #E2E8F0',
          borderRadius: 8,
          padding: '12px 14px',
          marginBottom: 18,
        }}
      >
        <p
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            color: '#475569',
          }}
        >
          How risks are found
        </p>
        <p style={{ margin: '6px 0 0', fontSize: 13.5, color: '#334155', lineHeight: 1.5 }}>
          The backend combines clinical interaction data with rule-based checks for duplicate ingredients, dose limits, schedule overlap, food/alcohol issues, and profile context such as allergies, kidney function, and liver status.
        </p>
        <p style={{ margin: '8px 0 0', fontSize: 12.5, color: '#475569', lineHeight: 1.5 }}>
          Risk categories: {Object.entries(kindCounts).length > 0 ? Object.entries(kindCounts).map(([key, value]) => `${key}: ${value}`).join(' · ') : 'No flagged categories yet.'}
        </p>
      </div>

      {/* ── Section label ────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 12,
        }}
      >
        <p
          style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.09em',
            textTransform: 'uppercase',
            color: '#9CA3AF',
          }}
        >
          {interactions.length} interaction{interactions.length !== 1 ? 's' : ''} detected
        </p>
        <p
          style={{
            fontSize: 11,
            fontWeight: 600,
            letterSpacing: '0.09em',
            textTransform: 'uppercase',
            color: '#9CA3AF',
          }}
        >
          Sorted by severity
        </p>
      </div>

      {/* ── Interaction list ─────────────────────────────────── */}
      {interactions.length === 0 ? (
        <div
          style={{
            background: '#fff',
            border: '1px solid #E5E7EB',
            borderRadius: 8,
            padding: '48px 24px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: '50%',
              background: '#ECFDF5',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}
          >
            <CheckCircle size={22} style={{ color: '#059669' }} />
          </div>
          <p style={{ fontWeight: 600, fontSize: 16, marginBottom: 6 }}>
            No interactions detected
          </p>
          <p style={{ fontSize: 14, color: '#6B7280', maxWidth: 380, margin: '0 auto' }}>
            Your current medication profile appears stable based on FDA clinical data. Always
            confirm with your pharmacist before any changes.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {sorted.map((inter, i) => (
            <InteractionRow
              key={i}
              ref={(node) => {
                rowRefs.current[i] = node;
              }}
              inter={inter}
              index={i}
              isExpanded={expandedInter === i}
              isSelected={selectedInteractionKey && [
                inter.kind || '',
                inter.severity || '',
                inter.drug_a || '',
                inter.drug_b || '',
                inter.summary || '',
              ].join('|').toLowerCase() === selectedInteractionKey}
              onToggle={() => setExpandedInter(expandedInter === i ? null : i)}
            />
          ))}
        </div>
      )}

      {/* ── Footer disclaimer ─────────────────────────────────── */}
      <div
        style={{
          marginTop: 32,
          padding: '14px 16px',
          background: '#F9FAFB',
          border: '1px solid #E5E7EB',
          borderRadius: 8,
          display: 'flex',
          gap: 10,
          alignItems: 'flex-start',
        }}
      >
        <Activity size={13} style={{ color: '#9CA3AF', flexShrink: 0, marginTop: 2 }} />
        <p style={{ fontSize: 12.5, color: '#6B7280', lineHeight: 1.55, margin: 0 }}>
          This report is generated from FDA cross-reference data and is for informational
          purposes only. It is not a substitute for professional medical advice. Always consult a
          licensed pharmacist or physician before adjusting any medication.
        </p>
      </div>
    </div>
  );
}