import React from 'react';
import { CheckCircle2, Clock, AlertTriangle, Lock } from 'lucide-react';

export default function FreshnessBadge({ state = 'fresh', lastReceived = null }) {
  let label = 'Fresh (<6h)';
  let cssClass = 'badge-fresh';
  let Icon = CheckCircle2;

  if (state === 'stale') {
    label = 'Stale (6-24h)';
    cssClass = 'badge-stale';
    Icon = Clock;
  } else if (state === 'missing') {
    label = 'Missing (>24h Data Gap)';
    cssClass = 'badge-missing';
    Icon = AlertTriangle;
  } else if (state === 'consent_restricted') {
    label = 'Consent Restricted';
    cssClass = 'badge-restricted';
    Icon = Lock;
  }

  return (
    <div className={`badge ${cssClass}`} style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.35rem',
      padding: '0.25rem 0.65rem',
      borderRadius: '9999px',
      fontSize: '0.75rem',
      fontWeight: 600,
      letterSpacing: '0.02em',
      textTransform: 'uppercase'
    }}>
      <Icon size={12} />
      <span>{label}</span>
    </div>
  );
}
