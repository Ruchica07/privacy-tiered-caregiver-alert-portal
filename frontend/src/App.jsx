import React, { useState, useEffect } from 'react';
import DisclaimerStrip from './components/DisclaimerStrip';
import RoleSelector from './components/RoleSelector';
import Dashboard from './components/Dashboard';
import Onboarding from './components/Onboarding';
import AdminAudit from './components/AdminAudit';
import MetricsDashboard from './components/MetricsDashboard';
import ErrorBoundary from './components/ErrorBoundary';
import { LayoutDashboard, Shield, History, BarChart2 } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const DEFAULT_CAREGIVERS = [
    { id: 'cg_001', name: 'Jane Smith', role: 'primary_caregiver' },
    { id: 'cg_002', name: 'Bob Smith', role: 'secondary_caregiver' },
    { id: 'cg_003', name: 'Maria Garcia', role: 'neighbor_community' },
    { id: 'cg_004', name: 'Dr. Sarah Chen', role: 'care_coordinator_professional' },
  ];

  const DEFAULT_RECIPIENTS = [
    { id: 'cr_001', name: 'Dorothy Thompson' },
    { id: 'cr_002', name: 'Harold Mitchell' },
    { id: 'cr_003', name: 'Margaret Williams' },
  ];

  const [caregivers, setCaregivers] = useState(DEFAULT_CAREGIVERS);
  const [careRecipients, setCareRecipients] = useState(DEFAULT_RECIPIENTS);
  const [selectedCaregiverId, setSelectedCaregiverId] = useState('cg_001');
  const [selectedRecipientId, setSelectedRecipientId] = useState('cr_001');

  const [alerts, setAlerts] = useState([]);
  const [accessSummary, setAccessSummary] = useState([]);
  const [consentMatrix, setConsentMatrix] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [evalResults, setEvalResults] = useState(null);
  const [loading, setLoading] = useState(false);

  // Load initial metadata (caregivers, recipients)
  useEffect(() => {
    fetch(`${API_BASE}/api/caregivers`)
      .then(res => res.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data?.caregivers || []);
        if (list.length > 0) {
          setCaregivers(list);
          setSelectedCaregiverId(list[0].id);
        }
      })
      .catch(() => {});

    fetch(`${API_BASE}/api/care-recipients`)
      .then(res => res.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data?.care_recipients || []);
        if (list.length > 0) {
          setCareRecipients(list);
          setSelectedRecipientId(list[0].id);
        }
      })
      .catch(() => {});

    fetch(`${API_BASE}/api/evaluation-metrics`)
      .then(res => res.json())
      .then(data => {
        if (data && data.metrics) {
          setEvalResults(data.metrics);
        }
      })
      .catch(() => {});
  }, []);

  // Fetch alerts & access summary when caregiver or recipient changes
  const loadAlertsAndConsent = () => {
    if (!selectedCaregiverId || !selectedRecipientId) return;
    setLoading(true);

    // Fetch alerts for selected caregiver
    fetch(`${API_BASE}/api/alerts?caregiver_id=${selectedCaregiverId}`)
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.alerts)) {
          // Filter to alerts belonging to selected recipient if present
          const userAlerts = data.alerts.filter(a => !a.care_recipient_id || a.care_recipient_id === selectedRecipientId);
          setAlerts(userAlerts);
        }
      })
      .catch(() => {
        // Fallback mock alerts
        setAlerts([
          {
            alert_id: 'a_001',
            care_recipient_id: selectedRecipientId,
            rule_fired: 'nocturnal_wandering',
            summary: 'Nocturnal Activity Outside Baseline',
            category: 'location_safety',
            severity: 'high',
            rendered_tier: 2,
            generated_at: new Date().toISOString(),
            evidence_summary: 'Nocturnal movement detected between 02:15 and 03:45 AM (3 occurrences this week, baseline = 0).',
            actionable_step: 'Check front door smart lock status or call Dorothy during morning check-in.',
            evidence_data: {
              trend_points: [
                { day: 'Mon', count: 0 },
                { day: 'Tue', count: 0 },
                { day: 'Wed', count: 1 },
                { day: 'Thu', count: 0 },
                { day: 'Fri', count: 3 },
                { day: 'Sat', count: 2 },
                { day: 'Sun', count: 4 },
              ]
            }
          },
          {
            alert_id: 'a_002',
            care_recipient_id: selectedRecipientId,
            rule_fired: 'missed_checkin',
            summary: 'Morning Check-In Delay',
            category: 'activity_engagement',
            severity: 'medium',
            rendered_tier: 1,
            generated_at: new Date(Date.now() - 3600000 * 2).toISOString(),
            evidence_summary: 'Morning check-in button has not been pressed for 4.5 hours past the expected 9:00 AM window.',
            actionable_step: 'Send a routine text check-in or place a casual phone call.'
          }
        ]);
      })
      .finally(() => setLoading(false));

    // Fetch access summary
    fetch(`${API_BASE}/api/access-summary?caregiver_id=${selectedCaregiverId}&care_recipient_id=${selectedRecipientId}`)
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.accessible_categories)) {
          const combined = [
            ...data.accessible_categories.map(c => ({
              category: c.category,
              consented_tier: c.tier,
              is_active: true
            })),
            ...(data.restricted_categories || []).map(c => ({
              category: c.category,
              consented_tier: 0,
              is_active: false
            }))
          ];
          setAccessSummary(combined);
        }
      })
      .catch(() => {
        setAccessSummary([
          { category: 'activity_engagement', consented_tier: 1, is_active: true },
          { category: 'location_safety', consented_tier: 2, is_active: true },
          { category: 'vitals_summary', consented_tier: 0, is_active: true },
          { category: 'social_isolation_signal', consented_tier: 1, is_active: true },
        ]);
      });

    // Fetch full consent matrix
    fetch(`${API_BASE}/api/consent/${selectedRecipientId}`)
      .then(res => res.json())
      .then(data => {
        if (data && Array.isArray(data.consent_matrix)) {
          setConsentMatrix(data.consent_matrix);
        }
      })
      .catch(() => {});

    // Fetch audit trail
    fetch(`${API_BASE}/api/audit/${selectedRecipientId}`)
      .then(res => res.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data?.audit_log || []);
        setAuditLogs(list);
      })
      .catch(() => {
        setAuditLogs([
          {
            audit_id: 'aud_001',
            timestamp: new Date().toISOString(),
            event_type: 'alert_filtered',
            actor_id: selectedCaregiverId,
            care_recipient_id: selectedRecipientId,
            details: { decision: 'rendered', category: 'location_safety', tier: 2 }
          },
          {
            audit_id: 'aud_002',
            timestamp: new Date(Date.now() - 7200000).toISOString(),
            event_type: 'consent_change',
            actor_id: 'system_proxy',
            care_recipient_id: selectedRecipientId,
            details: { category: 'location_safety', new_tier: 2, status: 'granted' }
          }
        ]);
      });
  };

  useEffect(() => {
    loadAlertsAndConsent();
  }, [selectedCaregiverId, selectedRecipientId]);

  const handleSaveConsent = (updatedMatrix) => {
    setConsentMatrix(updatedMatrix);
    fetch(`${API_BASE}/api/consent/${selectedRecipientId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        updates: updatedMatrix,
        actor_id: selectedCaregiverId || 'admin'
      })
    })
      .then(() => loadAlertsAndConsent())
      .catch(err => console.error('Consent save error:', err));
  };

  const fetchEvaluationMetrics = () => {
    fetch(`${API_BASE}/api/evaluation-metrics`)
      .then(res => res.json())
      .then(data => {
        if (data && data.metrics) {
          setEvalResults(data.metrics);
        }
      })
      .catch(() => {});
  };

  const handleRefreshRules = () => {
    setLoading(true);
    fetch(`${API_BASE}/api/run-rules-all`, { method: 'POST' })
      .finally(() => {
        loadAlertsAndConsent();
        fetchEvaluationMetrics();
      });
  };

  const currentCaregiver = caregivers.find(c => c.id === selectedCaregiverId) || caregivers[0] || { role: 'primary_caregiver' };

  return (
    <ErrorBoundary>
      <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column' }}>
        {/* Disclaimer Banner */}
        <DisclaimerStrip />

        {/* Role & Recipient Switcher */}
        <RoleSelector
          caregivers={caregivers}
          selectedCaregiverId={selectedCaregiverId}
          onSelectCaregiver={setSelectedCaregiverId}
          careRecipients={careRecipients}
          selectedRecipientId={selectedRecipientId}
          onSelectRecipient={setSelectedRecipientId}
        />

        {/* Navigation Tabs */}
        <div style={{ background: 'rgba(19, 27, 46, 0.6)', borderBottom: '1px solid var(--border-subtle)', padding: '0 1.5rem' }}>
          <div style={{ display: 'flex', gap: '1rem', overflowX: 'auto' }}>
            <button
              onClick={() => setActiveTab('dashboard')}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === 'dashboard' ? '3px solid #818cf8' : '3px solid transparent',
                color: activeTab === 'dashboard' ? '#818cf8' : '#94a3b8',
                padding: '0.85rem 0.5rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <LayoutDashboard size={16} />
              <span>Caregiver Alert Feed</span>
            </button>

            <button
              onClick={() => setActiveTab('onboarding')}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === 'onboarding' ? '3px solid #818cf8' : '3px solid transparent',
                color: activeTab === 'onboarding' ? '#818cf8' : '#94a3b8',
                padding: '0.85rem 0.5rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <Shield size={16} />
              <span>Consent & Privacy Matrix</span>
            </button>

            <button
              onClick={() => setActiveTab('audit')}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === 'audit' ? '3px solid #818cf8' : '3px solid transparent',
                color: activeTab === 'audit' ? '#818cf8' : '#94a3b8',
                padding: '0.85rem 0.5rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <History size={16} />
              <span>Audit Trail Log</span>
            </button>

            <button
              onClick={() => {
                setActiveTab('metrics');
                fetchEvaluationMetrics();
              }}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: activeTab === 'metrics' ? '3px solid #818cf8' : '3px solid transparent',
                color: activeTab === 'metrics' ? '#818cf8' : '#94a3b8',
                padding: '0.85rem 0.5rem',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem'
              }}
            >
              <BarChart2 size={16} />
              <span>Evaluation Metrics</span>
            </button>
          </div>
        </div>

        {/* Main Content Body */}
        <main style={{ flex: 1, padding: '1.5rem', maxWidth: '1280px', width: '100%', margin: '0 auto' }}>
          <ErrorBoundary>
            {activeTab === 'dashboard' && (
              <Dashboard
                alerts={alerts}
                accessSummary={accessSummary}
                caregiverRole={currentCaregiver.role}
                onRefresh={handleRefreshRules}
                loading={loading}
              />
            )}

            {activeTab === 'onboarding' && (
              <Onboarding
                caregivers={caregivers}
                consentMatrix={consentMatrix}
                onSaveConsent={handleSaveConsent}
              />
            )}

            {activeTab === 'audit' && (
              <AdminAudit auditLogs={auditLogs} />
            )}

            {activeTab === 'metrics' && (
              <MetricsDashboard evalResults={evalResults} />
            )}
          </ErrorBoundary>
        </main>
      </div>
    </ErrorBoundary>
  );
}
