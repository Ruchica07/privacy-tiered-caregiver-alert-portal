import React from 'react';
import { ShieldAlert, Info } from 'lucide-react';

export default function DisclaimerStrip() {
  return (
    <div style={{
      background: 'linear-gradient(90deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.15) 100%)',
      borderBottom: '1px solid rgba(99, 102, 241, 0.3)',
      padding: '0.6rem 1.25rem',
      fontSize: '0.825rem',
      color: '#c7d2fe',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '0.5rem'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <ShieldAlert size={16} color="#818cf8" />
        <span style={{ fontWeight: 600 }}>OPERATIONAL & WELLBEING SUPPORT PORTAL</span>
        <span style={{ color: '#9ca3af', margin: '0 0.25rem' }}>|</span>
        <span>Not a Medical Device or Emergency Medical Service (EMS) Dispatcher.</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#a5b4fc' }}>
        <Info size={14} />
        <span>Privacy-Tiered Category Consent Filter Active</span>
      </div>
    </div>
  );
}
