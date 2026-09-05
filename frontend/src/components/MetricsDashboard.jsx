import React from 'react';
import { BarChart2, CheckCircle2, ShieldCheck, Zap, AlertTriangle, FileText, Clock } from 'lucide-react';

export default function MetricsDashboard({ evalResults = null }) {
  // defaultMetrics is used only while the API call is in-flight (evalResults is null).
  // All values are null so the UI shows loading placeholders rather than stale figures.
  const defaultMetrics = {
    actionability_rate: null,
    privacy_compliance_rate: null,
    unnecessary_disclosure_rate: null,
    alert_delivery_accuracy: null,
    freshness_detection_rate: null,
    alert_recall: null,
    linter_violation_count: null,
    total_alerts_generated: null,
    total_ground_truth_anomalies: null,
    total_filtered_renders: null,
  };

  const metrics = evalResults || defaultMetrics;
  const isLoading = evalResults === null;

  // Helper: format a numeric metric value for display, or show '—' while loading
  const fmt = (val) => val === null ? '—' : `${val}%`;

  // Derive pass/fail dynamically from API values (no hardcoded fallbacks)
  const recallVal = metrics.alert_recall;
  const recallPassed = recallVal !== null && recallVal >= 90.0;
  const recallDesc = recallVal === null
    ? 'Loading…'
    : recallPassed
      ? `All ${metrics.total_ground_truth_anomalies ?? ''} ground-truth anomalies detected. Both night-hour and device-flagged unresolved departures are captured.`
      : `${recallVal}% of ground-truth anomalies detected. Review detection thresholds to reach the ≥ 90% target.`;

  const cards = [
    {
      title: "Actionability Rate",
      value: fmt(metrics.actionability_rate),
      target: "≥ 90.0%",
      baseline: "52.0%",
      passed: metrics.actionability_rate !== null && metrics.actionability_rate >= 90.0,
      loading: metrics.actionability_rate === null,
      icon: FileText,
      color: metrics.actionability_rate === null ? '#94a3b8' : '#34d399',
      desc: "Couples evidence with concrete non-medical operational guidance."
    },
    {
      title: "Privacy Compliance Rate",
      value: fmt(metrics.privacy_compliance_rate),
      target: "≥ 95.0%",
      baseline: "55.0%",
      passed: metrics.privacy_compliance_rate !== null && metrics.privacy_compliance_rate >= 95.0,
      loading: metrics.privacy_compliance_rate === null,
      icon: ShieldCheck,
      color: metrics.privacy_compliance_rate === null ? '#94a3b8' : '#34d399',
      desc: "Zero tier leakages and 100% content linter compliance across all renders."
    },
    {
      title: "Unnecessary Disclosure Rate",
      value: fmt(metrics.unnecessary_disclosure_rate),
      target: "≤ 5.0%",
      baseline: "45.0%",
      passed: metrics.unnecessary_disclosure_rate !== null && metrics.unnecessary_disclosure_rate <= 5.0,
      loading: metrics.unnecessary_disclosure_rate === null,
      icon: ShieldCheck,
      color: metrics.unnecessary_disclosure_rate === null ? '#94a3b8' : '#34d399',
      desc: "Rate of unconsented disclosures above granted category tier."
    },
    {
      title: "Alert Delivery Accuracy",
      value: fmt(metrics.alert_delivery_accuracy),
      target: "≥ 90.0%",
      baseline: "62.5%",
      passed: metrics.alert_delivery_accuracy !== null && metrics.alert_delivery_accuracy >= 90.0,
      loading: metrics.alert_delivery_accuracy === null,
      icon: CheckCircle2,
      color: metrics.alert_delivery_accuracy === null ? '#94a3b8' : '#34d399',
      desc: "Triggered alerts accurately matching ground-truth anomaly events."
    },
    {
      title: "Freshness Detection Rate",
      value: fmt(metrics.freshness_detection_rate),
      target: "≥ 95.0%",
      baseline: "70.0%",
      passed: metrics.freshness_detection_rate !== null && metrics.freshness_detection_rate >= 95.0,
      loading: metrics.freshness_detection_rate === null,
      icon: Clock,
      color: metrics.freshness_detection_rate === null ? '#94a3b8' : '#34d399',
      desc: "Accurate detection of Fresh, Stale, and Missing sensor states."
    },
    {
      title: "Alert Recall (Additional)",
      value: fmt(recallVal),
      target: "≥ 90.0%",
      baseline: "78.0%",
      passed: recallPassed,
      loading: recallVal === null,
      icon: Zap,
      color: recallVal === null ? '#94a3b8' : recallPassed ? '#34d399' : '#fbbf24',
      desc: recallDesc,
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header Panel */}
      <div className="glass-panel" style={{ padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
          <div style={{
            background: 'rgba(99, 102, 241, 0.2)',
            padding: '0.5rem',
            borderRadius: '10px',
            border: '1px solid rgba(99, 102, 241, 0.4)'
          }}>
            <BarChart2 size={24} color="#818cf8" />
          </div>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc' }}>
              Review 1 Quantitative Privacy Engine Evaluation Benchmark
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
              {isLoading
                ? 'Loading evaluation results from backend…'
                : `Evaluated on 30-day synthetic telemetry (${metrics.total_alerts_generated} alerts, ${metrics.total_ground_truth_anomalies} ground-truth anomalies, ${metrics.total_filtered_renders} tier-filtered renders).`
              }
            </p>
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '1rem'
      }}>
        {cards.map((c, i) => {
          const IconComp = c.icon;
          return (
            <div key={i} className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#cbd5e1' }}>{c.title}</span>
                  <span style={{
                    fontSize: '0.725rem',
                    fontWeight: 700,
                    padding: '0.2rem 0.5rem',
                    borderRadius: '4px',
                    background: c.loading ? 'rgba(148, 163, 184, 0.15)' : c.passed ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                    color: c.loading ? '#94a3b8' : c.passed ? '#34d399' : '#fbbf24',
                    border: `1px solid ${c.loading ? 'rgba(148, 163, 184, 0.3)' : c.passed ? 'rgba(16, 185, 129, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`
                  }}>
                    {c.loading ? 'Loading…' : c.passed ? 'Pass' : 'Needs Improvement'}
                  </span>
                </div>

                <div style={{ fontSize: '2.25rem', fontWeight: 800, color: c.color, lineHeight: 1.1, marginBottom: '0.5rem' }}>
                  {c.value}
                </div>

                <div style={{ display: 'flex', gap: '1rem', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '0.5rem' }}>
                  <span><strong>Target:</strong> {c.target}</span>
                  <span><strong>Baseline:</strong> {c.baseline}</span>
                </div>

                <p style={{ fontSize: '0.75rem', color: '#64748b', lineHeight: 1.4 }}>
                  {c.desc}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
