import React, { useState } from 'react';
import { History, Shield, Search, Lock, UserCheck, AlertTriangle } from 'lucide-react';

export default function AdminAudit({ auditLogs = [] }) {
  const [filterType, setFilterType] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');

  const logsList = Array.isArray(auditLogs)
    ? auditLogs
    : Array.isArray(auditLogs?.audit_log)
      ? auditLogs.audit_log
      : [];

  const filteredLogs = logsList.filter(log => {
    if (!log) return false;
    if (filterType !== 'all' && log.event_type !== filterType) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
      const actorMatch = (log.actor_id || '').toLowerCase().includes(q);
      const typeMatch = (log.event_type || '').toLowerCase().includes(q);
      const detailsMatch = JSON.stringify(log.details || {}).toLowerCase().includes(q);
      if (!actorMatch && !typeMatch && !detailsMatch) return false;
    }
    return true;
  });

  return (
    <div className="glass-panel" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <History color="#a78bfa" size={22} />
            Immutable Audit Trail & Regulatory Compliance Log
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8', marginTop: '0.2rem' }}>
            Complete transparent log of consent grants, alert filtering decisions, tier redactions, and access events.
          </p>
        </div>

        {/* Filter controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: '#0f172a',
            border: '1px solid #334155',
            borderRadius: '8px',
            padding: '0.4rem 0.75rem'
          }}>
            <Search size={14} color="#94a3b8" />
            <input
              type="text"
              placeholder="Search audit trail..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#f8fafc',
                fontSize: '0.825rem',
                outline: 'none'
              }}
            />
          </div>

          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{
              background: '#0f172a',
              color: '#cbd5e1',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '0.4rem 0.75rem',
              fontSize: '0.825rem',
              outline: 'none'
            }}
          >
            <option value="all">All Event Types</option>
            <option value="consent_change">Consent Changes</option>
            <option value="alert_filtered">Alert Filtering</option>
            <option value="alert_generated">Alert Generation</option>
            <option value="consent_expired">Consent Expirations</option>
          </select>
        </div>
      </div>

      {/* Audit Log Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem', color: '#cbd5e1' }}>
          <thead>
            <tr style={{ background: 'rgba(15, 23, 42, 0.8)', borderBottom: '1px solid rgba(255,255,255,0.1)', textAlign: 'left' }}>
              <th style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontWeight: 600 }}>Timestamp</th>
              <th style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontWeight: 600 }}>Event Type</th>
              <th style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontWeight: 600 }}>Actor</th>
              <th style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontWeight: 600 }}>Care Recipient</th>
              <th style={{ padding: '0.75rem 1rem', color: '#94a3b8', fontWeight: 600 }}>Decision & Event Details</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                  No audit log entries matching current criteria.
                </td>
              </tr>
            ) : (
              filteredLogs.map((log, idx) => (
                <tr key={log.audit_id || idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: idx % 2 === 0 ? 'transparent' : 'rgba(15, 23, 42, 0.4)' }}>
                  <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap', color: '#94a3b8' }}>
                    {log.timestamp ? new Date(log.timestamp).toLocaleString() : 'Just now'}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                    <span style={{
                      padding: '0.15rem 0.5rem',
                      borderRadius: '4px',
                      fontSize: '0.725rem',
                      fontWeight: 600,
                      background: log.event_type === 'consent_change' ? 'rgba(99,102,241,0.2)' : 'rgba(168,85,247,0.2)',
                      color: log.event_type === 'consent_change' ? '#818cf8' : '#c084fc',
                      border: `1px solid ${log.event_type === 'consent_change' ? 'rgba(99,102,241,0.4)' : 'rgba(168,85,247,0.4)'}`
                    }}>
                      {log.event_type ? log.event_type.replace(/_/g, ' ').toUpperCase() : 'EVENT'}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 500, color: '#f1f5f9' }}>
                    {log.actor_id}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>
                    {log.care_recipient_id}
                  </td>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', fontSize: '0.775rem', color: '#94a3b8' }}>
                    {JSON.stringify(log.details || {})}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
