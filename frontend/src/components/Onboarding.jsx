import React from 'react';
import ConsentGrid from './ConsentGrid';
import { UserPlus, ShieldCheck, Info } from 'lucide-react';

export default function Onboarding({ caregivers, consentMatrix, onSaveConsent }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Onboarding Intro Banner */}
      <div className="glass-panel" style={{ padding: '1.5rem', background: 'linear-gradient(135deg, rgba(23,32,54,0.8) 0%, rgba(30,41,69,0.8) 100%)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
          <div style={{
            background: 'rgba(99, 102, 241, 0.2)',
            padding: '0.5rem',
            borderRadius: '10px',
            border: '1px solid rgba(99,102,241,0.4)'
          }}>
            <ShieldCheck size={24} color="#818cf8" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
              Care Recipient Consent & Role Management
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              Empowering older adults and legal proxies to maintain dignity, privacy, and control over shared information.
            </p>
          </div>
        </div>

        <div style={{
          marginTop: '1rem',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '0.75rem'
        }}>
          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#818cf8', marginBottom: '0.2rem' }}>
              1. Minimum Necessary Rule
            </h4>
            <p style={{ fontSize: '0.775rem', color: '#cbd5e1' }}>
              Caregivers only receive disclosure tiers required for their explicit caregiving role.
            </p>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#a78bfa', marginBottom: '0.2rem' }}>
              2. Revocable & Dynamic
            </h4>
            <p style={{ fontSize: '0.775rem', color: '#cbd5e1' }}>
              Consent can be updated or revoked mid-stream at any time with immediate effect.
            </p>
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)' }}>
            <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#34d399', marginBottom: '0.2rem' }}>
              3. Immutable Audit Log
            </h4>
            <p style={{ fontSize: '0.775rem', color: '#cbd5e1' }}>
              Every consent update generates a timestamped entry in the audit trail.
            </p>
          </div>
        </div>
      </div>

      {/* Main Consent Matrix Grid */}
      <ConsentGrid
        caregivers={caregivers}
        consentMatrix={consentMatrix}
        onSaveConsent={onSaveConsent}
      />
    </div>
  );
}
