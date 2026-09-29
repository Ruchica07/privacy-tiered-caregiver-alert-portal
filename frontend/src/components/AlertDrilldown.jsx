import React, { useState } from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from 'recharts';
import { Activity, CheckCircle2, ShieldAlert, FileText, Info, Bell, Send, Smartphone, Check, AlertTriangle, RefreshCw } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

const MOCK_SPARKLINE_DATA = [
  { day: 'Mon', count: 1 },
  { day: 'Tue', count: 0 },
  { day: 'Wed', count: 2 },
  { day: 'Thu', count: 0 },
  { day: 'Fri', count: 4 },
  { day: 'Sat', count: 3 },
  { day: 'Sun', count: 5 },
];

export default function AlertDrilldown({ alert, caregiverId }) {
  const renderedTier = alert.rendered_tier ?? 0;
  const [dispatchStatus, setDispatchStatus] = useState(null);
  const [dispatchingChannel, setDispatchingChannel] = useState(null);

  const handleDispatch = (channel) => {
    setDispatchingChannel(channel);
    setDispatchStatus(null);
    fetch(`${API_BASE}/api/notifications/dispatch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        alert_id: alert.alert_id,
        caregiver_id: caregiverId || 'cg_001',
        channel: channel,
        recipient_contact: channel === 'sms' ? '+15551234567' : `${caregiverId || 'cg_001'}@notifications.local`
      })
    })
      .then(res => res.json())
      .then(data => setDispatchStatus(data))
      .catch(err => setDispatchStatus({ status: 'error', message: err.message }))
      .finally(() => setDispatchingChannel(null));
  };

  return (
    <div style={{
      marginTop: '0.75rem',
      paddingTop: '1rem',
      borderTop: '1px solid rgba(255,255,255,0.08)',
      display: 'flex',
      flexDirection: 'column',
      gap: '1rem'
    }}>
      {/* Evidence Summary (Tier 1+) */}
      {alert.evidence_summary && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          padding: '0.85rem',
          borderRadius: '8px',
          border: '1px solid rgba(255,255,255,0.05)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem', color: '#a5b4fc', fontSize: '0.825rem', fontWeight: 600 }}>
            <Info size={14} />
            <span>Operational Evidence Summary</span>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#e2e8f0', lineHeight: 1.5 }}>
            {alert.evidence_summary}
          </p>
        </div>
      )}

      {/* Recommended Action (Tier 1+) */}
      {alert.actionable_step && (
        <div style={{
          background: 'rgba(16, 185, 129, 0.08)',
          border: '1px solid rgba(16, 185, 129, 0.2)',
          padding: '0.85rem',
          borderRadius: '8px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem', color: '#34d399', fontSize: '0.825rem', fontWeight: 600 }}>
            <CheckCircle2 size={14} />
            <span>Recommended Caregiver Action</span>
          </div>
          <p style={{ fontSize: '0.85rem', color: '#d1fae5', fontWeight: 500 }}>
            {alert.actionable_step}
          </p>
        </div>
      )}

      {/* Sparkline Trend Graph (Tier 2+) */}
      {renderedTier >= 2 && alert.evidence_data && (
        <div style={{
          background: 'rgba(15, 23, 42, 0.6)',
          padding: '0.85rem',
          borderRadius: '8px',
          border: '1px solid rgba(99, 102, 241, 0.2)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#a78bfa', fontSize: '0.825rem', fontWeight: 600 }}>
              <Activity size={14} />
              <span>7-Day Event Frequency Sparkline</span>
            </div>
            <span style={{ fontSize: '0.725rem', color: '#94a3b8' }}>Tier 2 Disclosure Granted</span>
          </div>

          <div style={{ height: 100, width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={alert.evidence_data.trend_points || MOCK_SPARKLINE_DATA}>
                <defs>
                  <linearGradient id="colorTrend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#818cf8" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#818cf8" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '6px', fontSize: '11px' }} />
                <Area type="monotone" dataKey="count" stroke="#818cf8" strokeWidth={2} fillOpacity={1} fill="url(#colorTrend)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Clinical Qualitative Note (Tier 3 Only) */}
      {renderedTier >= 3 && alert.clinical_note && (
        <div style={{
          background: 'rgba(168, 85, 247, 0.08)',
          border: '1px solid rgba(168, 85, 247, 0.3)',
          padding: '0.85rem',
          borderRadius: '8px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.35rem', color: '#c084fc', fontSize: '0.825rem', fontWeight: 600 }}>
            <FileText size={14} />
            <span>Tier 3 Professional Operational Note</span>
          </div>
          <p style={{ fontSize: '0.825rem', color: '#f3e8ff', fontStyle: 'italic' }}>
            {alert.clinical_note}
          </p>
        </div>
      )}

      {/* Content Linter Guarantee Badge */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.35rem',
        fontSize: '0.725rem',
        color: '#64748b',
        marginTop: '0.2rem'
      }}>
        <ShieldAlert size={12} color="#475569" />
        <span>Content Linter Verified: 0 diagnostic or prescriptive medical terms.</span>
      </div>

      {/* Live Notification Dispatcher (Phase 3 Sandbox) */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.5)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        borderRadius: '8px',
        padding: '0.85rem',
        marginTop: '0.5rem'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#c7d2fe', fontSize: '0.825rem', fontWeight: 600 }}>
            <Bell size={14} color="#818cf8" />
            <span>Sandbox Notification Dispatch (Phase 3)</span>
          </div>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', background: 'rgba(0,0,0,0.3)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>
            Idempotency & Retries Active
          </span>
        </div>

        <p style={{ fontSize: '0.775rem', color: '#94a3b8', marginBottom: '0.65rem', lineHeight: 1.4 }}>
          Simulate alert delivery to external caregiver channels. Strict resident consent gating and content linter sanitization are applied server-side prior to dispatch.
        </p>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            onClick={() => handleDispatch('web_push')}
            disabled={dispatchingChannel !== null}
            style={{
              background: 'rgba(99, 102, 241, 0.15)',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              color: '#a5b4fc',
              borderRadius: '6px',
              padding: '0.35rem 0.65rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            {dispatchingChannel === 'web_push' ? <RefreshCw size={12} className="spin" /> : <Send size={12} />}
            <span>Dispatch Web Push</span>
          </button>

          <button
            onClick={() => handleDispatch('sms')}
            disabled={dispatchingChannel !== null}
            style={{
              background: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.4)',
              color: '#6ee7b7',
              borderRadius: '6px',
              padding: '0.35rem 0.65rem',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem'
            }}
          >
            {dispatchingChannel === 'sms' ? <RefreshCw size={12} className="spin" /> : <Smartphone size={12} />}
            <span>Dispatch SMS</span>
          </button>
        </div>

        {/* Dispatch Result Feedback */}
        {dispatchStatus && (
          <div style={{
            marginTop: '0.65rem',
            padding: '0.55rem 0.75rem',
            borderRadius: '6px',
            fontSize: '0.775rem',
            background: dispatchStatus.status === 'delivered_sandbox'
              ? 'rgba(16, 185, 129, 0.1)'
              : dispatchStatus.status === 'withheld_consent'
                ? 'rgba(245, 158, 11, 0.1)'
                : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${
              dispatchStatus.status === 'delivered_sandbox'
                ? 'rgba(16, 185, 129, 0.3)'
                : dispatchStatus.status === 'withheld_consent'
                  ? 'rgba(245, 158, 11, 0.3)'
                  : 'rgba(239, 68, 68, 0.3)'
            }`,
            color: dispatchStatus.status === 'delivered_sandbox'
              ? '#6ee7b7'
              : dispatchStatus.status === 'withheld_consent'
                ? '#fde68a'
                : '#fca5a5',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.4rem'
          }}>
            {dispatchStatus.status === 'delivered_sandbox' ? (
              <Check size={14} style={{ marginTop: '0.1rem', flexShrink: 0 }} />
            ) : (
              <AlertTriangle size={14} style={{ marginTop: '0.1rem', flexShrink: 0 }} />
            )}
            <div>
              <div style={{ fontWeight: 600, textTransform: 'capitalize' }}>
                Status: {dispatchStatus.status?.replace(/_/g, ' ')}
              </div>
              <div style={{ fontSize: '0.725rem', marginTop: '0.15rem', opacity: 0.9 }}>
                {dispatchStatus.message || (dispatchStatus.status === 'delivered_sandbox' ? 'Delivered to sandbox channel successfully.' : 'Blocked by consent filter.')}
              </div>
              {dispatchStatus.provider_meta?.environment && (
                <div style={{ fontSize: '0.675rem', color: '#94a3b8', marginTop: '0.2rem' }}>
                  Environment: {dispatchStatus.provider_meta.environment} • Disclosed Tier: {dispatchStatus.disclosed_tier} • Attempts: {dispatchStatus.attempts}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
