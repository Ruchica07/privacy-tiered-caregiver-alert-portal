import React from 'react';
import { AlertCircle, AlertTriangle, Info, ChevronDown, ChevronUp, Lock, ShieldCheck, Activity } from 'lucide-react';
import FreshnessBadge from './FreshnessBadge';

const SEVERITY_STYLES = {
  low: { bg: 'rgba(16, 185, 129, 0.12)', border: 'rgba(16, 185, 129, 0.3)', text: '#34d399', icon: Info },
  medium: { bg: 'rgba(245, 158, 11, 0.12)', border: 'rgba(245, 158, 11, 0.3)', text: '#fbbf24', icon: AlertTriangle },
  high: { bg: 'rgba(239, 68, 68, 0.12)', border: 'rgba(239, 68, 68, 0.3)', text: '#f87171', icon: AlertCircle },
  critical: { bg: 'rgba(168, 85, 247, 0.15)', border: 'rgba(168, 85, 247, 0.4)', text: '#c084fc', icon: AlertCircle },
};

export default function AlertCard({ alert, isExpanded, onToggleExpand }) {
  const severityStyle = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.medium;
  const SevIcon = severityStyle.icon;

  const renderedTier = alert.rendered_tier ?? 0;
  const isDataGap = alert.is_data_gap;

  return (
    <div className="glass-card" style={{
      borderLeft: `4px solid ${severityStyle.border}`,
      marginBottom: '1rem',
      position: 'relative'
    }}>
      {/* Header Row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{
            background: severityStyle.bg,
            border: `1px solid ${severityStyle.border}`,
            padding: '0.45rem',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <SevIcon size={18} color={severityStyle.text} />
          </div>
          <div>
            <h4 style={{ fontSize: '1.025rem', fontWeight: 600, color: '#f8fafc' }}>
              {alert.summary || alert.rule_fired?.replace(/_/g, ' ')}
            </h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
              <span style={{
                fontSize: '0.725rem',
                color: '#94a3b8',
                background: 'rgba(0,0,0,0.3)',
                padding: '0.1rem 0.4rem',
                borderRadius: '4px'
              }}>
                {alert.category ? alert.category.replace(/_/g, ' ').toUpperCase() : 'GENERAL'}
              </span>
              <span style={{ fontSize: '0.725rem', color: '#64748b' }}>•</span>
              <span style={{ fontSize: '0.725rem', color: '#64748b' }}>
                {new Date(alert.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        </div>

        {/* Badges Right */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FreshnessBadge state={isDataGap ? 'missing' : 'fresh'} />
          <span style={{
            fontSize: '0.7rem',
            fontWeight: 700,
            color: renderedTier > 0 ? '#a78bfa' : '#9ca3af',
            background: 'rgba(0,0,0,0.4)',
            padding: '0.2rem 0.5rem',
            borderRadius: '6px',
            border: '1px solid rgba(255,255,255,0.08)',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem'
          }}>
            {renderedTier === 0 ? <Lock size={10} /> : <ShieldCheck size={10} />}
            Tier {renderedTier}
          </span>
        </div>
      </div>

      {/* Tier 0 Fallback Notice */}
      {renderedTier === 0 && (
        <div style={{
          marginTop: '0.85rem',
          padding: '0.65rem 0.85rem',
          background: 'rgba(30, 41, 59, 0.5)',
          borderRadius: '6px',
          fontSize: '0.8rem',
          color: '#94a3b8',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }}>
          <Lock size={14} color="#64748b" />
          <span>Detailed evidence restricted by Care Recipient Consent Matrix (Tier 0 Wellness Ping).</span>
        </div>
      )}

      {/* Expand / Collapse Button */}
      {renderedTier > 0 && (
        <div style={{ marginTop: '0.85rem', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={onToggleExpand}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#818cf8',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
              padding: '0.2rem 0.5rem',
              borderRadius: '4px'
            }}
          >
            <span>{isExpanded ? 'Hide Details' : 'View Evidence & Trend'}</span>
            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        </div>
      )}
    </div>
  );
}
