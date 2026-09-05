import React, { useState } from 'react';
import { Shield, Save, CheckCircle, HelpCircle, Lock, Eye, Activity, FileText } from 'lucide-react';

const CATEGORIES = [
  { key: 'activity_engagement', name: 'Activity & Routine', desc: 'Check-in delays, daily movement scores, routine patterns' },
  { key: 'location_safety', name: 'Location & Safety', desc: 'Geofence boundaries, night door opening events' },
  { key: 'social_isolation_signal', name: 'Social Interaction', desc: 'Phone call frequencies, visitor check-in logs' },
  { key: 'vitals_summary', name: 'Vitals & Motion Trends', desc: 'Heartbeat sensor data gaps, activity level trends' },
  { key: 'medication_adherence', name: 'Medication Dispenser', desc: 'Smart pillbox opening timestamps' },
  { key: 'diagnosis_conditions', name: 'Care Plan Context', desc: 'General care coordinator notes (Tier 3 restricted)' },
];

const TIER_OPTIONS = [
  { tier: 0, label: 'Tier 0 — Wellness Ping', icon: Lock },
  { tier: 1, label: 'Tier 1 — Category Detail', icon: Eye },
  { tier: 2, label: 'Tier 2 — Detailed Trends', icon: Activity },
  { tier: 3, label: 'Tier 3 — Full Operational Context', icon: FileText },
];

export default function ConsentGrid({ caregivers = [], consentMatrix = [], onSaveConsent }) {
  const [selectedCaregiverId, setSelectedCaregiverId] = useState(caregivers[0]?.id || '');
  const [localMatrix, setLocalMatrix] = useState(consentMatrix);
  const [saveMessage, setSaveMessage] = useState(false);

  React.useEffect(() => {
    if (Array.isArray(consentMatrix)) {
      setLocalMatrix(consentMatrix);
    }
  }, [consentMatrix]);

  React.useEffect(() => {
    if (caregivers.length > 0 && !selectedCaregiverId) {
      setSelectedCaregiverId(caregivers[0].id);
    }
  }, [caregivers]);

  const selectedCaregiver = caregivers.find(c => c.id === selectedCaregiverId) || caregivers[0];

  const handleTierChange = (categoryKey, newTier) => {
    setLocalMatrix(prev => {
      const arr = Array.isArray(prev) ? prev : [];
      const existing = arr.find(c => c.caregiver_id === selectedCaregiverId && c.category === categoryKey);
      if (existing) {
        return arr.map(c => c.caregiver_id === selectedCaregiverId && c.category === categoryKey
          ? { ...c, max_tier: newTier, consent_status: 'granted' }
          : c
        );
      } else {
        return [...arr, {
          consent_id: `c_${Date.now()}`,
          caregiver_id: selectedCaregiverId,
          category: categoryKey,
          max_tier: newTier,
          consent_status: 'granted',
          granted_at: new Date().toISOString()
        }];
      }
    });
  };

  const handleSave = () => {
    onSaveConsent(localMatrix);
    setSaveMessage(true);
    setTimeout(() => setSaveMessage(false), 3000);
  };

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Shield color="#818cf8" size={22} />
            Consent & Privacy Matrix Setup
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Configure exact information category permissions for each designated caregiver.
          </p>
        </div>

        <button
          onClick={handleSave}
          style={{
            background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
            color: '#fff',
            border: 'none',
            borderRadius: '8px',
            padding: '0.55rem 1.25rem',
            fontSize: '0.875rem',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)'
          }}
        >
          <Save size={16} />
          <span>Save Consent Settings</span>
        </button>
      </div>

      {saveMessage && (
        <div style={{
          background: 'rgba(16, 185, 129, 0.15)',
          border: '1px solid #10b981',
          color: '#34d399',
          padding: '0.65rem 1rem',
          borderRadius: '8px',
          marginBottom: '1rem',
          fontSize: '0.85rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }}>
          <CheckCircle size={16} />
          <span>Consent Matrix saved successfully! Audit log entry created.</span>
        </div>
      )}

      {/* Caregiver Selector Tabs */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '0.75rem', marginBottom: '1.25rem', overflowX: 'auto' }}>
        {caregivers.map(c => (
          <button
            key={c.id}
            onClick={() => setSelectedCaregiverId(c.id)}
            style={{
              background: selectedCaregiverId === c.id ? 'rgba(99, 102, 241, 0.2)' : 'transparent',
              color: selectedCaregiverId === c.id ? '#818cf8' : '#94a3b8',
              border: `1px solid ${selectedCaregiverId === c.id ? 'rgba(99, 102, 241, 0.4)' : 'transparent'}`,
              borderRadius: '8px',
              padding: '0.45rem 0.85rem',
              fontSize: '0.825rem',
              fontWeight: 600,
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {c.name} ({c.role.replace(/_/g, ' ')})
          </button>
        ))}
      </div>

      {/* Category Grid */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {CATEGORIES.map(cat => {
          const currentRecord = localMatrix.find(
            c => c.caregiver_id === selectedCaregiverId && c.category === cat.key
          );
          const activeTier = currentRecord ? currentRecord.max_tier : 0;

          return (
            <div key={cat.key} style={{
              background: 'rgba(15, 23, 42, 0.6)',
              border: '1px solid rgba(255,255,255,0.05)',
              borderRadius: '10px',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.75rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div>
                  <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
                    {cat.name}
                  </h4>
                  <p style={{ fontSize: '0.775rem', color: '#94a3b8' }}>
                    {cat.desc}
                  </p>
                </div>
                <span style={{ fontSize: '0.75rem', color: '#a5b4fc', background: 'rgba(99, 102, 241, 0.15)', padding: '0.15rem 0.5rem', borderRadius: '4px' }}>
                  Current: Tier {activeTier}
                </span>
              </div>

              {/* Tier Radio Options */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '0.5rem'
              }}>
                {TIER_OPTIONS.map(opt => {
                  const isSelected = activeTier === opt.tier;
                  const IconComp = opt.icon;

                  return (
                    <button
                      key={opt.tier}
                      onClick={() => handleTierChange(cat.key, opt.tier)}
                      style={{
                        background: isSelected ? 'rgba(99, 102, 241, 0.25)' : 'rgba(30, 41, 59, 0.4)',
                        border: `1px solid ${isSelected ? '#818cf8' : 'rgba(255,255,255,0.08)'}`,
                        borderRadius: '6px',
                        padding: '0.5rem 0.75rem',
                        color: isSelected ? '#f8fafc' : '#94a3b8',
                        fontSize: '0.775rem',
                        fontWeight: isSelected ? 600 : 400,
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.4rem',
                        textAlign: 'left'
                      }}
                    >
                      <IconComp size={14} color={isSelected ? '#818cf8' : '#64748b'} />
                      <span>{opt.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
