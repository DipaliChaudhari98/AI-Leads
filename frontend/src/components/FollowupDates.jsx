import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Calendar, RefreshCcw } from 'lucide-react';

const FollowupDates = () => {
    const [leads, setLeads] = useState([]);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const limit = 50;

    const fetchData = async () => {
        try {
            const res = await axios.get(`/api/leads?page=${page}&limit=${limit}`);
            setLeads(res.data.data);
            setTotal(res.data.total);
        } catch (err) {
            console.error('Failed to fetch leads:', err);
        }
    };

    useEffect(() => {
        fetchData();
    }, [page]);


    const handleDateChange = async (leadId, newDate) => {
        if (!newDate) return;
        try {
            await axios.put(`/api/leads/${leadId}/initial-date`, { initial_date: newDate });
            fetchData();
        } catch (err) {
            console.error('Failed to update date:', err);
            alert('Failed to update date');
        }
    };

    return (
        <div className="fade-in">
            <div className="ui-card">
                <div className="card-header followup-header" style={{ borderBottom: '1px solid var(--border)', paddingBottom: '1.5rem', marginBottom: '1.5rem' }}>
                    <h2>Follow-up Dates</h2>
                    <p className="text-muted" style={{ marginTop: '0.25rem' }}>
                        Edit initial email dates and track scheduled follow-ups for your leads.
                    </p>
                </div>
                <div className="table-container">
                    <table className="ui-table w-full">
                        <thead>
                            <tr>
                                <th>Lead / Company</th>
                                <th>Timezone</th>
                                <th>Initial Email Scheduled</th>
                                <th>Follow-up 1 (Local)</th>
                                <th>Follow-up 2 (Local)</th>
                                <th>UTC Time (Initial)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {!leads || leads.length === 0 ? (
                                <tr>
                                    <td colSpan="6">
                                        <div className="empty-state" style={{ padding: '3rem 1rem', background: 'transparent', border: 'none' }}>
                                            <Calendar size={48} className="text-muted" strokeWidth={1} />
                                            <p style={{ marginTop: '1rem' }}>No leads found.</p>
                                            <span className="text-muted text-sm">Launch a campaign to see follow-up dates here.</span>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                leads.map(lead => {
                                    // Parse to YYYY-MM-DDTHH:mm format for datetime-local input
                                    let initialDateVal = '';
                                    let utcString = 'Not Scheduled';
                                    let leadTz = lead.timezone || 'UTC';
                                    let offsetStr = lead.utc_offset ? ` (UTC${lead.utc_offset > 0 ? '+' : ''}${lead.utc_offset})` : '';

                                    if (lead.initial_email_date) {
                                        const d = new Date(lead.initial_email_date);
                                        if (!isNaN(d.getTime())) {
                                            const tzOffset = d.getTimezoneOffset() * 60000;
                                            initialDateVal = (new Date(d - tzOffset)).toISOString().slice(0, 16);
                                            utcString = d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
                                        }
                                    }

                                    // Format with time explicitly in the lead's timezone
                                    const formatLeadLocalTime = (dateStr) => {
                                        if (!dateStr) return 'Not Scheduled';
                                        const d = new Date(dateStr);
                                        if (isNaN(d.getTime())) return 'Invalid Date';
                                        
                                        try {
                                            return d.toLocaleString('en-US', {
                                                timeZone: leadTz,
                                                month: 'short', day: 'numeric',
                                                hour: 'numeric', minute: '2-digit',
                                                timeZoneName: 'short'
                                            });
                                        } catch (e) {
                                            return d.toLocaleString(undefined, {
                                                month: 'short', day: 'numeric',
                                                hour: 'numeric', minute: '2-digit'
                                            });
                                        }
                                    };

                                    const nextDate = formatLeadLocalTime(lead.next_followup_date);
                                    const lastDate = formatLeadLocalTime(lead.last_followup_date);
                                    const leadInitial = (lead.name || '?').charAt(0);

                                    return (
                                        <tr key={lead.id}>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                                    <div className="lead-avatar" style={{ width: '32px', height: '32px', fontSize: '0.8rem', borderRadius: '50%', background: 'var(--primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                        {leadInitial}
                                                    </div>
                                                    <div>
                                                        <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{lead.name || '-'}</div>
                                                        <div className="text-muted text-sm" style={{ marginTop: '0.1rem' }}>{lead.title ? lead.title + ' @ ' : ''}{lead.company || '-'}</div>
                                                        <div className="text-muted text-sm" style={{ marginTop: '0.1rem', fontSize: '0.7rem' }}>{lead.email || '-'}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td>
                                                <div style={{ fontSize: '0.85rem' }}>{leadTz}</div>
                                                <div className="text-muted" style={{ fontSize: '0.75rem' }}>{offsetStr.replace('(', '').replace(')', '')}</div>
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <input
                                                        type="datetime-local"
                                                        className="ui-input"
                                                        style={{ padding: '0.25rem 0.5rem', borderRadius: '4px', fontFamily: 'inherit', fontSize: '0.8rem', background: 'var(--card)', border: '1px solid var(--border)', color: 'var(--foreground)' }}
                                                        value={initialDateVal}
                                                        onChange={(e) => handleDateChange(lead.id, e.target.value)}
                                                    />
                                                </div>
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: 'white' }}>
                                                    <Calendar size={14} className="text-muted" />
                                                    {nextDate}
                                                </div>
                                            </td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: 'white' }}>
                                                    <RefreshCcw size={14} className="text-muted" />
                                                    {lastDate}
                                                </div>
                                            </td>
                                            <td>
                                                <div style={{ fontSize: '0.85rem', color: 'var(--muted-foreground)', fontFamily: 'monospace' }}>
                                                    {utcString}
                                                </div>
                                            </td>
                                        </tr>
                                    );
                                })
                            )}
                        </tbody>
                    </table>
                </div>
                {total > limit && (
                    <div className="pagination-controls" style={{ display: 'flex', justifyContent: 'center', gap: '1rem', padding: '1rem', borderTop: '1px solid var(--border)' }}>
                        <button className="btn btn-outline" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
                        <span style={{ display: 'flex', alignItems: 'center', fontSize: '0.9rem', color: 'var(--muted-foreground)' }}>Page {page} of {Math.ceil(total / limit)}</span>
                        <button className="btn btn-outline" disabled={page >= Math.ceil(total / limit)} onClick={() => setPage(page + 1)}>Next</button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FollowupDates;
