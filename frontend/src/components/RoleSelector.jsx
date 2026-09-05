import React from 'react';
import { UserCheck, Users, HeartHandshake } from 'lucide-react';

export default function RoleSelector({
  caregivers = [],
  selectedCaregiverId,
  onSelectCaregiver,
  careRecipients = [],
  selectedRecipientId,
  onSelectRecipient
}) {
  const currentCaregiver = caregivers.find(c => c.id === selectedCaregiverId) || caregivers[0];

  return (
    <div style={{
      background: 'rgba(19, 27, 46, 0.9)',
      borderBottom: '1px solid var(--border-subtle)',
      padding: '0.85rem 1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      flexWrap: 'wrap',
      gap: '1rem'
    }}>
      {/* Brand & App title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(99, 102, 241, 0.3)'
        }}>
          <HeartHandshake size={22} color="#fff" />
        </div>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', lineHeight: 1.2 }}>
            AegisCare <span style={{ color: '#818cf8', fontWeight: 400, fontSize: '0.85rem' }}>v1.0</span>
          </h1>
          <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
            Privacy-Tiered Caregiver Alert Portal
          </p>
        </div>
      </div>

      {/* Selectors for Caregiver & Care Recipient */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        {/* Care Recipient Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Users size={16} color="#94a3b8" />
          <span style={{ fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 500 }}>Recipient:</span>
          <select
            value={selectedRecipientId || ''}
            onChange={(e) => onSelectRecipient(e.target.value)}
            style={{
              background: '#0f172a',
              color: '#f8fafc',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '0.4rem 0.75rem',
              fontSize: '0.825rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {careRecipients.map(r => (
              <option key={r.id} value={r.id}>
                {r.name} ({r.id})
              </option>
            ))}
          </select>
        </div>

        {/* Caregiver Role Switcher (Mock Auth) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <UserCheck size={16} color="#818cf8" />
          <span style={{ fontSize: '0.8rem', color: '#cbd5e1', fontWeight: 500 }}>Logged in as:</span>
          <select
            value={selectedCaregiverId || ''}
            onChange={(e) => onSelectCaregiver(e.target.value)}
            style={{
              background: '#0f172a',
              color: '#818cf8',
              fontWeight: 600,
              border: '1px solid rgba(99, 102, 241, 0.4)',
              borderRadius: '8px',
              padding: '0.4rem 0.75rem',
              fontSize: '0.825rem',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            {caregivers.map(c => (
              <option key={c.id} value={c.id}>
                {c.name} — {c.role.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}
