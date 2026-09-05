import React, { useState } from 'react';
import AlertCard from './AlertCard';
import AlertDrilldown from './AlertDrilldown';
import TierBanner from './TierBanner';
import { Filter, Search, RefreshCw, CheckCircle2, ShieldAlert } from 'lucide-react';

export default function Dashboard({
  alerts = [],
  accessSummary = [],
  caregiverRole = '',
  onRefresh,
  loading = false
}) {
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedAlertId, setExpandedAlertId] = useState(null);

  const filteredAlerts = alerts.filter(alert => {
    if (selectedCategory !== 'all' && alert.category !== selectedCategory) return false;
    if (selectedSeverity !== 'all' && alert.severity !== selectedSeverity) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const summaryMatch = (alert.summary || '').toLowerCase().includes(q);
      const catMatch = (alert.category || '').toLowerCase().includes(q);
      const ruleMatch = (alert.rule_fired || '').toLowerCase().includes(q);
      if (!summaryMatch && !catMatch && !ruleMatch) return false;
    }
    return true;
  });

  return (
    <div>
      {/* Tier & Access Level Banner */}
      <TierBanner caregiverRole={caregiverRole} accessSummary={accessSummary} />

      {/* Filter & Controls Bar */}
      <div className="glass-panel" style={{ padding: '1rem 1.25rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap', flex: 1 }}>
            {/* Search Bar */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: '#0f172a',
              border: '1px solid #334155',
              borderRadius: '8px',
              padding: '0.4rem 0.75rem',
              minWidth: '220px'
            }}>
              <Search size={15} color="#94a3b8" />
              <input
                type="text"
                placeholder="Search alerts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#f8fafc',
                  fontSize: '0.825rem',
                  outline: 'none',
                  width: '100%'
                }}
              />
            </div>

            {/* Category Filter */}
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
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
              <option value="all">All Categories</option>
              <option value="activity_engagement">Activity & Routine</option>
              <option value="location_safety">Location & Safety</option>
              <option value="social_isolation_signal">Social Interaction</option>
              <option value="vitals_summary">Vitals & Sensors</option>
              <option value="medication_adherence">Medication Adherence</option>
            </select>

            {/* Severity Filter */}
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
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
              <option value="all">All Severities</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>

          <button
            onClick={onRefresh}
            disabled={loading}
            style={{
              background: 'rgba(99, 102, 241, 0.2)',
              color: '#818cf8',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              borderRadius: '8px',
              padding: '0.4rem 0.85rem',
              fontSize: '0.825rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem'
            }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Refresh Rules</span>
          </button>
        </div>
      </div>

      {/* Alert Feed Section */}
      {filteredAlerts.length === 0 ? (
        <div className="glass-panel" style={{ padding: '3rem 2rem', textAlign: 'center' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'rgba(16, 185, 129, 0.15)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1rem'
          }}>
            <CheckCircle2 size={24} color="#34d399" />
          </div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.35rem' }}>
            No Active Operational Alerts
          </h3>
          <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '420px', margin: '0 auto' }}>
            All monitored routines and sensor telemetry are operating within normal baseline parameters.
          </p>
        </div>
      ) : (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#cbd5e1' }}>
              Active Alerts ({filteredAlerts.length})
            </h3>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
              Newest first • Tier-filtered render
            </span>
          </div>

          {filteredAlerts.map(alert => {
            const isExp = expandedAlertId === alert.alert_id;
            return (
              <div key={alert.alert_id}>
                <AlertCard
                  alert={alert}
                  isExpanded={isExp}
                  onToggleExpand={() => setExpandedAlertId(isExp ? null : alert.alert_id)}
                />
                {isExp && alert.rendered_tier > 0 && (
                  <div style={{ marginTop: '-0.5rem', marginBottom: '1.25rem', paddingLeft: '1rem', borderLeft: '2px dashed rgba(99,102,241,0.4)' }}>
                    <AlertDrilldown alert={alert} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
