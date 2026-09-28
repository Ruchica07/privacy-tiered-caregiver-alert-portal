import React, { useState, useEffect } from 'react';
import { Users, AlertTriangle, CheckCircle, WifiOff, Shield, ArrowRight, Activity, Heart, Eye } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function FleetDashboard({ onSelectRecipient, onSwitchToFeed }) {
  const [fleet, setFleet] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchFleet = () => {
    setLoading(true);
    fetch(`${API_BASE}/api/fleet-overview`)
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.fleet)) {
          setFleet(data.fleet);
        }
      })
      .catch(() => {
        // Fallback demo fleet data
        setFleet([
          {
            care_recipient_id: 'cr_001',
            name: 'Dorothy Thompson',
            status_badge: 'Attention Needed',
            status_type: 'warning',
            freshness: 'fresh',
            total_active_alerts: 2,
            severity_counts: { critical: 0, high: 1, medium: 1, low: 0 },
            overall_tier_label: 'Tier 2 (Evidence & Trends)',
            baseline_activity_mean: 55.0,
            accessible_categories_count: 5,
          },
          {
            care_recipient_id: 'cr_002',
            name: 'Harold Mitchell',
            status_badge: 'Operational Normal',
            status_type: 'normal',
            freshness: 'fresh',
            total_active_alerts: 0,
            severity_counts: { critical: 0, high: 0, medium: 0, low: 0 },
            overall_tier_label: 'Tier 3 (Full Clinical Note)',
            baseline_activity_mean: 62.0,
            accessible_categories_count: 6,
          },
          {
            care_recipient_id: 'cr_003',
            name: 'Margaret Williams',
            status_badge: 'Device Offline',
            status_type: 'missing',
            freshness: 'missing',
            total_active_alerts: 1,
            severity_counts: { critical: 0, high: 0, medium: 1, low: 0 },
            overall_tier_label: 'Tier 1 (Categorical Summary)',
            baseline_activity_mean: 48.0,
            accessible_categories_count: 4,
          }
        ]);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFleet();
  }, []);

  const totalSeniors = fleet.length;
  const attentionCount = fleet.filter(f => f.status_type === 'warning').length;
  const normalCount = fleet.filter(f => f.status_type === 'normal').length;
  const offlineCount = fleet.filter(f => f.status_type === 'missing').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* KPI Overview Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
        <div className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Total Monitored Seniors</span>
            <Users size={18} color="#818cf8" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.5rem' }}>
            {totalSeniors}
          </div>
          <span style={{ fontSize: '0.725rem', color: '#64748b' }}>Assigned to Care Fleet</span>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid #f59e0b' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#f59e0b', fontWeight: 600 }}>Attention Needed</span>
            <AlertTriangle size={18} color="#f59e0b" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#f59e0b', marginTop: '0.5rem' }}>
            {attentionCount}
          </div>
          <span style={{ fontSize: '0.725rem', color: '#64748b' }}>Active Operational Alerts</span>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid #10b981' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600 }}>Operational Normal</span>
            <CheckCircle size={18} color="#10b981" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#10b981', marginTop: '0.5rem' }}>
            {normalCount}
          </div>
          <span style={{ fontSize: '0.725rem', color: '#64748b' }}>Baseline Routine Maintained</span>
        </div>

        <div className="glass-panel" style={{ padding: '1.25rem', borderLeft: '3px solid #ef4444' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.8rem', color: '#ef4444', fontWeight: 600 }}>Device Offline</span>
            <WifiOff size={18} color="#ef4444" />
          </div>
          <div style={{ fontSize: '1.75rem', fontWeight: 700, color: '#ef4444', marginTop: '0.5rem' }}>
            {offlineCount}
          </div>
          <span style={{ fontSize: '0.725rem', color: '#64748b' }}>Telemetry Gaps ({'>'}24h)</span>
        </div>
      </div>

      {/* Fleet Grid */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield color="#818cf8" size={20} />
              Multi-Resident Coordinator Fleet Grid
            </h2>
            <p style={{ fontSize: '0.825rem', color: '#94a3b8', marginTop: '0.2rem' }}>
              Real-time privacy-compliant oversight across all care recipients under professional coordination.
            </p>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
          {fleet.map((r) => (
            <div
              key={r.care_recipient_id}
              style={{
                background: 'rgba(15, 23, 42, 0.7)',
                border: `1px solid ${
                  r.status_type === 'warning' ? 'rgba(245, 158, 11, 0.4)' :
                  r.status_type === 'missing' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(255, 255, 255, 0.08)'
                }`,
                borderRadius: '12px',
                padding: '1.25rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                transition: 'all 0.2s ease',
              }}
            >
              <div>
                {/* Header: Name & Status Pill */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                  <div>
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                      {r.name}
                    </h3>
                    <span style={{ fontSize: '0.725rem', color: '#64748b' }}>ID: {r.care_recipient_id}</span>
                  </div>

                  <span style={{
                    padding: '0.25rem 0.6rem',
                    borderRadius: '9999px',
                    fontSize: '0.725rem',
                    fontWeight: 600,
                    background: r.status_type === 'warning' ? 'rgba(245, 158, 11, 0.2)' :
                                r.status_type === 'missing' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                    color: r.status_type === 'warning' ? '#fbbf24' :
                           r.status_type === 'missing' ? '#f87171' : '#34d399',
                    border: `1px solid ${
                      r.status_type === 'warning' ? 'rgba(245, 158, 11, 0.4)' :
                      r.status_type === 'missing' ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'
                    }`,
                  }}>
                    {r.status_badge}
                  </span>
                </div>

                {/* Metrics Breakdown */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', margin: '0.75rem 0', fontSize: '0.775rem' }}>
                  <div style={{ background: '#090d16', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b', display: 'block' }}>Active Alerts</span>
                    <strong style={{ color: r.total_active_alerts > 0 ? '#f59e0b' : '#10b981', fontSize: '1rem' }}>
                      {r.total_active_alerts}
                    </strong>
                  </div>
                  <div style={{ background: '#090d16', padding: '0.5rem 0.75rem', borderRadius: '6px' }}>
                    <span style={{ color: '#64748b', display: 'block' }}>Consented Tiers</span>
                    <strong style={{ color: '#818cf8', fontSize: '0.85rem' }}>
                      {r.accessible_categories_count} Categories
                    </strong>
                  </div>
                </div>

                {/* Privacy Access Banner */}
                <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '1rem' }}>
                  <span style={{ color: '#64748b' }}>Privacy Cap: </span>
                  <span style={{ color: '#cbd5e1' }}>{r.overall_tier_label}</span>
                </div>
              </div>

              {/* Action Button */}
              <button
                onClick={() => {
                  if (onSelectRecipient) onSelectRecipient(r.care_recipient_id);
                  if (onSwitchToFeed) onSwitchToFeed();
                }}
                style={{
                  width: '100%',
                  background: 'rgba(99, 102, 241, 0.15)',
                  border: '1px solid rgba(99, 102, 241, 0.4)',
                  color: '#a5b4fc',
                  padding: '0.6rem',
                  borderRadius: '8px',
                  fontSize: '0.825rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '0.4rem',
                  transition: 'background 0.2s ease',
                }}
              >
                <Eye size={15} />
                <span>Inspect Resident Feed</span>
                <ArrowRight size={15} />
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
