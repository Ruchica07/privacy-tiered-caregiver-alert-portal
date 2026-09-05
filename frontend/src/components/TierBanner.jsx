import React from 'react';
import { Shield, Eye, Lock, FileText, Activity } from 'lucide-react';

const TIER_DESCRIPTIONS = {
  0: { title: "Tier 0 — Wellness Ping", desc: "No specific category detail or evidence. Operational ping only.", icon: Lock, color: "#9ca3af" },
  1: { title: "Tier 1 — Category Detail", desc: "Category type and general non-clinical status message.", icon: Eye, color: "#60a5fa" },
  2: { title: "Tier 2 — Detailed Trends", desc: "Visual trend sparklines, behavioral frequency & evidence summary.", icon: Activity, color: "#a78bfa" },
  3: { title: "Tier 3 — Full Operational Context", desc: "Complete trend history & qualitative operational notes.", icon: FileText, color: "#34d399" },
};

export default function TierBanner({ caregiverRole = '', accessSummary = [] }) {
  const summaryList = Array.isArray(accessSummary) ? accessSummary : [];

  return (
    <div className="glass-panel" style={{ padding: '1rem 1.25rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Shield size={20} color="#818cf8" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f3f4f6' }}>
            Your Active Privacy & Disclosure Boundaries
          </h3>
        </div>
        <span style={{
          fontSize: '0.75rem',
          background: 'rgba(99, 102, 241, 0.2)',
          color: '#a5b4fc',
          padding: '0.2rem 0.6rem',
          borderRadius: '6px',
          border: '1px solid rgba(99, 102, 241, 0.3)',
          fontWeight: 600
        }}>
          Role: {(caregiverRole || '').replace(/_/g, ' ').toUpperCase()}
        </span>
      </div>

      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '0.75rem'
      }}>
        {summaryList.map((item, idx) => {
          const tier = item.consented_tier ?? item.tier ?? 0;
          const tierInfo = TIER_DESCRIPTIONS[tier] || TIER_DESCRIPTIONS[0];
          const IconComp = tierInfo.icon;
          const catName = (item.category || item.category_name || 'general').replace(/_/g, ' ').toUpperCase();

          return (
            <div key={idx} style={{
              background: 'rgba(15, 23, 42, 0.6)',
              border: `1px solid ${item.is_active !== false ? 'rgba(255,255,255,0.08)' : 'rgba(239,68,68,0.3)'}`,
              borderRadius: '8px',
              padding: '0.65rem 0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.25rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#e2e8f0' }}>
                  {catName}
                </span>
                <span style={{
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  color: tierInfo.color,
                  background: 'rgba(0,0,0,0.3)',
                  padding: '0.15rem 0.4rem',
                  borderRadius: '4px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.2rem'
                }}>
                  <IconComp size={11} /> Tier {item.consented_tier}
                </span>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                {tierInfo.desc}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
