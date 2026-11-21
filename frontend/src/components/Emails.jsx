import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useSearchParams } from 'react-router-dom';
import { Mail, Edit2, Save, X, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const TYPE_ORDER = { initial: 1, follow_up_1: 2, follow_up_2: 3, follow_up_3: 4 };
const TYPE_LABELS = {
  initial: 'Initial Email',
  follow_up_1: 'Follow-up 1',
  follow_up_2: 'Follow-up 2',
  follow_up_3: 'Follow-up 3',
};
const TYPE_COLOR = {
  initial:     { bg: '#1e40af22', border: '#3b82f6', text: '#60a5fa' },
  follow_up_1: { bg: '#713f1222', border: '#f59e0b', text: '#fbbf24' },
  follow_up_2: { bg: '#14532d22', border: '#22c55e', text: '#4ade80' },
  follow_up_3: { bg: '#581c8722', border: '#a855f7', text: '#c084fc' },
};

function formatDate(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch { return iso; }
}

const Emails = () => {
  const [searchParams] = useSearchParams();
  const leadId = searchParams.get('lead_id');

  const [emails, setEmails] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Inline editing
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({ subject: '', body: '' });
  const [isSaving, setIsSaving] = useState(false);

  // Collapsed lead cards (default: all expanded)
  const [collapsed, setCollapsed] = useState(new Set());

  const limit = 50;

  // ── Fetch newest emails from dedicated endpoint ──────────────
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append('page', page);
      params.append('limit', limit);
      if (leadId) {
        params.append('lead_id', leadId);
      }
      const res = await axios.get(`/api/follow_ups/emails?${params.toString()}`);
      setEmails(res.data.data || []);
      setTotal(res.data.total || 0);
    } catch (err) {
      console.error('Failed to fetch emails:', err);
      setError('Failed to load emails. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [page, leadId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // ── Group by lead email (show only the latest generated email sequence for each lead) ──
  const groups = (() => {
    const map = {};
    emails.forEach(e => {
      const key = e.email || e.lead_name || 'unknown';
      if (!map[key]) {
        map[key] = {
          key,
          lead_name: e.lead_name,
          company: e.company,
          title: e.title,
          industry: e.industry,
          email: e.email,
          lead_status: e.lead_status,
          latest_scheduled: e.scheduled_at || '',
          emails: [],
        };
      }
      if (e.scheduled_at && e.scheduled_at > map[key].latest_scheduled) {
        map[key].latest_scheduled = e.scheduled_at;
      }
      map[key].emails.push(e);
    });

    return Object.values(map)
      .map(g => {
        // Sort emails by type order (initial -> follow_up_1 -> follow_up_2 -> etc)
        g.emails.sort((a, b) => (TYPE_ORDER[a.followup_type] || 99) - (TYPE_ORDER[b.followup_type] || 99));
        return g;
      })
      // Newest-generated group first
      .sort((a, b) => (b.latest_scheduled > a.latest_scheduled ? 1 : -1));
  })();

  // ── Edit helpers ─────────────────────────────────────────────
  const handleEditClick = (email) => {
    setEditingId(email.email_id);
    setEditForm({ subject: email.subject || '', body: email.body || '' });
  };
  const handleCancelEdit = () => { setEditingId(null); setEditForm({ subject: '', body: '' }); };
  const handleSave = async (emailId) => {
    setIsSaving(true);
    try {
      await axios.put(`/api/follow_ups/${emailId}`, editForm);
      setEditingId(null);
      fetchData();
    } catch (err) {
      console.error('Save failed:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleCollapse = (key) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const totalPages = Math.ceil(total / limit);

  // ── Render ───────────────────────────────────────────────────
  return (
    <div className="fade-in">
      <div className="ui-card">

        {/* Header */}
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
          borderBottom: '1px solid var(--border)', paddingBottom: '1.25rem', marginBottom: '1.5rem'
        }}>
          <div>
            <h2 style={{ margin: 0 }}>Generated Emails</h2>
            <p className="text-muted text-sm" style={{ marginTop: '0.25rem' }}>
              {total.toLocaleString()} emails in database · Latest sequences first
            </p>
          </div>
          <button className="btn btn-outline" onClick={fetchData} title="Refresh">
            <RefreshCw size={15} />
          </button>
        </div>

        {/* States */}
        {loading && (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted-foreground)' }}>
            <div className="loader" style={{ margin: '0 auto 1rem' }} />
            Loading emails…
          </div>
        )}
        {!loading && error && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#f87171' }}>{error}</div>
        )}
        {!loading && !error && groups.length === 0 && (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--muted-foreground)' }}>
            <Mail size={40} strokeWidth={1} style={{ margin: '0 auto 1rem', display: 'block', opacity: 0.5 }} />
            <p>No emails generated yet.</p>
            <span style={{ fontSize: '0.85rem' }}>Run a campaign to generate outreach sequences.</span>
          </div>
        )}

        {/* Email groups */}
        {!loading && !error && groups.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {groups.map((group) => {
              const isCollapsed = collapsed.has(group.key);
              const initial = (group.lead_name || '?').charAt(0).toUpperCase();
              const latestDate = formatDate(group.latest_scheduled);

              return (
                <div key={group.key} style={{
                  border: '1px solid var(--border)',
                  borderRadius: '10px',
                  overflow: 'hidden',
                  background: 'var(--card)',
                }}>

                  {/* Lead card header */}
                  <div
                    onClick={() => toggleCollapse(group.key)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '0.85rem',
                      padding: '0.9rem 1.25rem', cursor: 'pointer',
                      background: 'var(--card-hover)',
                      borderBottom: isCollapsed ? 'none' : '1px solid var(--border)',
                      transition: 'background 0.15s',
                    }}
                  >
                    {/* Avatar */}
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%',
                      background: 'var(--primary)', color: 'white',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontWeight: 700, fontSize: '0.85rem', flexShrink: 0
                    }}>{initial}</div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                          {group.lead_name || 'Unknown'}
                        </span>
                        {group.company && (
                          <span className="text-muted" style={{ fontSize: '0.82rem' }}>@ {group.company}</span>
                        )}
                        {group.title && (
                          <span className="text-muted" style={{ fontSize: '0.78rem' }}>· {group.title}</span>
                        )}
                      </div>
                      <div className="text-muted" style={{ fontSize: '0.78rem', marginTop: '0.1rem' }}>
                        {group.email || ''}
                        {group.industry ? ` · ${group.industry}` : ''}
                      </div>
                    </div>

                    {/* Meta */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
                      <span style={{ fontSize: '0.78rem', color: 'var(--muted-foreground)' }}>
                        {group.emails.length} email{group.emails.length !== 1 ? 's' : ''}
                        {latestDate ? ` · ${latestDate}` : ''}
                      </span>
                      {isCollapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
                    </div>
                  </div>

                  {/* Emails */}
                  {!isCollapsed && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                      {group.emails.map((email, idx) => {
                        const colors = TYPE_COLOR[email.followup_type] || TYPE_COLOR.initial;
                        const isEditing = editingId === email.email_id;
                        const scheduledFmt = formatDate(email.scheduled_at);
                        const sentFmt = formatDate(email.sent_at);

                        return (
                          <div key={email.email_id} style={{
                            borderTop: idx > 0 ? '1px solid var(--border)' : 'none',
                            padding: '1.1rem 1.25rem',
                          }}>
                            {/* Email sub-header */}
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                {/* Type badge */}
                                <span style={{
                                  fontSize: '0.72rem', fontWeight: 600, padding: '0.2rem 0.55rem',
                                  borderRadius: 4, border: `1px solid ${colors.border}`,
                                  background: colors.bg, color: colors.text, textTransform: 'uppercase', letterSpacing: '0.04em'
                                }}>
                                  {TYPE_LABELS[email.followup_type] || email.followup_type}
                                </span>

                                {/* Status badge */}
                                <span className={`status-badge ${email.status === 'sent' || email.status === 'EMAIL_SENT' ? 'status-approved' : 'status-pending'}`} style={{ fontSize: '0.72rem' }}>
                                  {(email.status || 'draft').toUpperCase()}
                                </span>

                                {/* Date info */}
                                {sentFmt && (
                                  <span style={{ fontSize: '0.75rem', color: '#4ade80' }}>✓ Sent {sentFmt}</span>
                                )}
                                {!sentFmt && scheduledFmt && (
                                  <span style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>
                                    📅 {scheduledFmt}
                                  </span>
                                )}
                              </div>

                              {/* Edit button */}
                              {!isEditing ? (
                                <button
                                  className="btn btn-secondary"
                                  onClick={() => handleEditClick(email)}
                                  style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                                >
                                  <Edit2 size={12} /> Edit
                                </button>
                              ) : (
                                <div style={{ display: 'flex', gap: '0.35rem' }}>
                                  <button
                                    className="btn btn-primary"
                                    onClick={() => handleSave(email.email_id)}
                                    disabled={isSaving}
                                    style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                                  >
                                    <Save size={12} /> {isSaving ? 'Saving…' : 'Save'}
                                  </button>
                                  <button
                                    className="btn btn-secondary"
                                    onClick={handleCancelEdit}
                                    disabled={isSaving}
                                    style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                                  >
                                    <X size={12} /> Cancel
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Email content */}
                            {isEditing ? (
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                <div>
                                  <label style={{ display: 'block', fontSize: '0.78rem', marginBottom: '0.25rem', color: 'var(--muted-foreground)' }}>Subject</label>
                                  <input
                                    type="text"
                                    className="ui-input"
                                    style={{ width: '100%' }}
                                    value={editForm.subject}
                                    onChange={e => setEditForm({ ...editForm, subject: e.target.value })}
                                  />
                                </div>
                                <div>
                                  <label style={{ display: 'block', fontSize: '0.78rem', marginBottom: '0.25rem', color: 'var(--muted-foreground)' }}>Body</label>
                                  <textarea
                                    className="ui-input"
                                    style={{ width: '100%', minHeight: 140, resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.55 }}
                                    value={editForm.body}
                                    onChange={e => setEditForm({ ...editForm, body: e.target.value })}
                                  />
                                </div>
                              </div>
                            ) : (
                              <div style={{
                                background: 'var(--background)',
                                border: '1px solid var(--border)',
                                borderRadius: 6,
                                padding: '0.85rem 1rem',
                              }}>
                                <div style={{
                                  fontWeight: 600, fontSize: '0.875rem',
                                  paddingBottom: '0.6rem', marginBottom: '0.6rem',
                                  borderBottom: '1px solid var(--border)',
                                  color: 'var(--foreground)'
                                }}>
                                  {email.subject || '(No Subject)'}
                                </div>
                                <div style={{
                                  whiteSpace: 'pre-wrap', lineHeight: 1.65,
                                  fontSize: '0.875rem', color: 'var(--muted-foreground)'
                                }}>
                                  {email.body || '(No body content)'}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{
            display: 'flex', justifyContent: 'center', alignItems: 'center',
            gap: '1rem', padding: '1rem 0', borderTop: '1px solid var(--border)', marginTop: '1rem'
          }}>
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

export default Emails;
