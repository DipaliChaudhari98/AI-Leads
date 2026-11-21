import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Mail, Settings, RefreshCw } from 'lucide-react';

const TYPE_LABELS = {
  initial: 'Initial',
  follow_up_1: 'Follow-up 1',
  follow_up_2: 'Follow-up 2',
  follow_up_3: 'Follow-up 3',
};

const STATUS_CLASS = {
  draft: 'status-pending',
  processing: 'status-active',
  sent: 'status-approved',
  EMAIL_SENT: 'status-approved',
  researched: 'status-active',
  new: 'status-pending',
};

const Followups = () => {
  const [followups, setFollowups] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [isProcessing, setIsProcessing] = useState(false);
  const limit = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`/api/follow_ups?page=${page}&limit=${limit}`);
      setFollowups(res.data.data || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Failed to fetch follow-ups:', err);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const toggleCheckbox = (id) => {
    const next = new Set(selectedIds);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedIds(next);
  };

  const toggleAll = (e) => {
    setSelectedIds(e.target.checked ? new Set(followups.map(f => f.email_id)) : new Set());
  };

  const handleProcessSelected = async () => {
    if (selectedIds.size === 0) return;
    setIsProcessing(true);
    try {
      await axios.post('/api/follow_ups/process', { email_ids: Array.from(selectedIds) });
      setSelectedIds(new Set());
      fetchData();
    } catch (error) {
      console.error('Error processing:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="fade-in">
      <div className="ui-card">

        {/* ── Header ─────────────────────────────────────────── */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
          borderBottom: '1px solid var(--border)', paddingBottom: '1.25rem', marginBottom: '1.25rem'
        }}>
          <div>
            <h2 style={{ margin: 0 }}>Follow-up Management</h2>
            <p className="text-muted text-sm" style={{ marginTop: '0.25rem' }}>
              {total.toLocaleString()} total outreach records
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-outline" onClick={fetchData} title="Refresh">
              <RefreshCw size={15} />
            </button>
            <button
              className="btn btn-primary"
              onClick={handleProcessSelected}
              disabled={isProcessing || selectedIds.size === 0}
            >
              <Settings size={15} style={{ marginRight: '0.4rem' }} />
              {isProcessing ? 'Processing…' : `Process${selectedIds.size > 0 ? ` (${selectedIds.size})` : ''}`}
            </button>
          </div>
        </div>

        {/* ── Table ──────────────────────────────────────────── */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted-foreground)' }}>
            Loading…
          </div>
        ) : followups.length === 0 ? (
          <div className="empty-state" style={{ padding: '3rem', textAlign: 'center', border: 'none', background: 'transparent' }}>
            <Mail size={40} className="text-muted" strokeWidth={1} style={{ margin: '0 auto' }} />
            <p style={{ marginTop: '0.75rem' }}>No follow-ups scheduled yet.</p>
            <span className="text-muted text-sm">Run a campaign to generate email sequences.</span>
          </div>
        ) : (
          <div className="table-container">
            <table className="ui-table w-full">
              <thead>
                <tr>
                  <th style={{ width: 36, textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      className="ui-checkbox"
                      onChange={toggleAll}
                      checked={followups.length > 0 && selectedIds.size === followups.length}
                    />
                  </th>
                  <th>Lead</th>
                  <th>Email</th>
                  <th>Type</th>
                  <th>Lead Status</th>
                  <th>Email Status</th>
                  <th>Scheduled</th>
                </tr>
              </thead>
              <tbody>
                {followups.map(f => {
                  const initial = (f.lead_name || '?').charAt(0).toUpperCase();
                  const typeLabel = TYPE_LABELS[f.followup_type] || (f.followup_type || '—').replace(/_/g, ' ');
                  const scheduled = f.scheduled_at
                    ? new Date(f.scheduled_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })
                    : '—';
                  const sent = f.sent_at
                    ? new Date(f.sent_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
                    : null;

                  return (
                    <tr key={f.email_id}>
                      <td style={{ textAlign: 'center' }}>
                        <input
                          type="checkbox"
                          className="ui-checkbox"
                          checked={selectedIds.has(f.email_id)}
                          onChange={() => toggleCheckbox(f.email_id)}
                        />
                      </td>

                      {/* Lead + company */}
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                          <div style={{
                            width: 30, height: 30, borderRadius: '50%',
                            background: 'var(--primary)', color: 'white',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontWeight: 700, fontSize: '0.75rem', flexShrink: 0
                          }}>{initial}</div>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: '0.875rem', lineHeight: 1.2 }}>
                              {f.lead_name || '—'}
                            </div>
                            <div className="text-muted" style={{ fontSize: '0.75rem' }}>
                              {f.company || '—'}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Email address */}
                      <td style={{ fontSize: '0.82rem', color: 'var(--muted-foreground)' }}>
                        {f.email || '—'}
                      </td>

                      {/* Outreach type */}
                      <td>
                        <span className="status-badge status-active" style={{ fontSize: '0.75rem' }}>
                          {typeLabel}
                        </span>
                      </td>

                      {/* Lead status */}
                      <td>
                        <span className={`status-badge ${STATUS_CLASS[f.lead_status] || 'status-pending'}`} style={{ fontSize: '0.75rem' }}>
                          {(f.lead_status || '—').replace(/_/g, ' ')}
                        </span>
                      </td>

                      {/* Email status */}
                      <td>
                        <span className={`status-badge ${STATUS_CLASS[f.status] || 'status-pending'}`} style={{ fontSize: '0.75rem' }}>
                          {(f.status || 'draft').toUpperCase()}
                        </span>
                      </td>

                      {/* Scheduled / sent date */}
                      <td style={{ fontSize: '0.82rem', color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>
                        {sent ? (
                          <span title="Sent">✓ {sent}</span>
                        ) : (
                          scheduled
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Pagination ─────────────────────────────────────── */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '1rem', padding: '1rem', borderTop: '1px solid var(--border)', marginTop: '0.5rem' }}>
            <button className="btn btn-outline" disabled={page === 1} onClick={() => setPage(p => p - 1)}>← Prev</button>
            <span style={{ fontSize: '0.875rem', color: 'var(--muted-foreground)' }}>
              Page {page} of {totalPages}
            </span>
            <button className="btn btn-outline" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next →</button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Followups;
