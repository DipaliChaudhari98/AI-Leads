import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { Filter, Mail } from 'lucide-react';

const LeadsTable = () => {
    const [leads, setLeads] = useState([]);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    // Filters
    const [locationFilter, setLocationFilter] = useState('');
    const [industryFilter, setIndustryFilter] = useState('');
    const [dateFrom, setDateFrom] = useState('');
    const [dateTo, setDateTo] = useState('');

    const fetchLeads = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (locationFilter) params.append('location', locationFilter);
            if (industryFilter) params.append('industry', industryFilter);
            if (dateFrom) params.append('date_from', new Date(dateFrom).toISOString());
            if (dateTo) params.append('date_to', new Date(dateTo).toISOString());

            const res = await axios.get(`/api/leads?${params.toString()}`);
            setLeads(res.data.data || res.data);
        } catch (err) {
            console.error('Failed to fetch leads:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLeads();
    }, [locationFilter, industryFilter, dateFrom, dateTo]);

    // Navigates to the same Emails tab, pre-filtered to this lead's generated
    // sequence — reuses the existing /emails page/query, just scoped by lead_id.
    const handleViewEmails = (leadId) => {
        navigate(`/emails?lead_id=${leadId}`);
    };

    return (
        <div className="fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <div>
                    <h1>Leads Directory</h1>
                    <p className="text-muted">All leads fetched via Apollo and their current status.</p>
                </div>
            </div>

            <div className="ui-card" style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'var(--background)', padding: '0.5rem 1rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
                        <Filter size={16} className="text-muted" />
                        <span className="text-muted">Filters:</span>
                    </div>

                    <input
                        type="text"
                        placeholder="Location"
                        className="ui-input"
                        style={{ width: '200px' }}
                        value={locationFilter}
                        onChange={(e) => setLocationFilter(e.target.value)}
                    />

                    <input
                        type="text"
                        placeholder="Industry"
                        className="ui-input"
                        style={{ width: '200px' }}
                        value={industryFilter}
                        onChange={(e) => setIndustryFilter(e.target.value)}
                    />

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className="text-muted">From:</span>
                        <input
                            type="date"
                            className="ui-input"
                            value={dateFrom}
                            onChange={(e) => setDateFrom(e.target.value)}
                        />
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className="text-muted">To:</span>
                        <input
                            type="date"
                            className="ui-input"
                            value={dateTo}
                            onChange={(e) => setDateTo(e.target.value)}
                        />
                    </div>
                </div>
            </div>

            <div className="ui-card" style={{ overflowX: 'auto' }}>
                {loading ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }}>Loading leads...</div>
                ) : leads.length === 0 ? (
                    <div style={{ padding: '2rem', textAlign: 'center' }} className="text-muted">No leads found matching your criteria.</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid var(--border)' }}>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Date Added</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Name</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Title</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Company</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Location</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Business Hours</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Initial Mail Schedule</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Pain Points</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Status</th>
                                <th style={{ padding: '1rem', color: 'var(--muted)' }}>Emails</th>
                            </tr>
                        </thead>
                        <tbody>
                            {leads.map(lead => {
                                const locationParts = [lead.city, lead.state, lead.country].filter(Boolean);
                                const locationDisplay = locationParts.length > 0 ? locationParts.join(', ') : (lead.location || 'N/A');

                                const businessHoursDisplay = (lead.business_hours_start && lead.business_hours_end)
                                    ? `${lead.business_hours_start} - ${lead.business_hours_end}`
                                    : 'N/A';

                                let initialScheduleDisplay = 'N/A';
                                if (lead.initial_email_date) {
                                    initialScheduleDisplay = lead.initial_email_date + (lead.timezone ? ` (${lead.timezone})` : '');
                                }

                                const painPoints = Array.isArray(lead.pain_points) ? lead.pain_points : [];

                                return (
                                    <tr key={lead.id} style={{ borderBottom: '1px solid var(--border)' }}>
                                        <td style={{ padding: '1rem' }}>
                                            {lead.created_at ? new Date(lead.created_at).toLocaleDateString() : 'N/A'}
                                        </td>
                                        <td style={{ padding: '1rem', fontWeight: '500' }}>
                                            {lead.name}
                                            <div style={{ fontSize: '0.8rem', color: 'var(--muted)' }}>{lead.email}</div>
                                        </td>
                                        <td style={{ padding: '1rem' }}>{lead.title}</td>
                                        <td style={{ padding: '1rem' }}>{lead.company}</td>
                                        <td style={{ padding: '1rem' }}>{locationDisplay}</td>
                                        <td style={{ padding: '1rem' }}>{businessHoursDisplay}</td>
                                        <td style={{ padding: '1rem' }}>{initialScheduleDisplay}</td>
                                        <td style={{ padding: '1rem', maxWidth: '250px' }}>
                                            {painPoints.length > 0 ? (
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem' }}>
                                                    {painPoints.map((pt, idx) => (
                                                        <div key={idx} style={{ fontSize: '0.8rem', background: 'var(--background)', padding: '0.35rem 0.5rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
                                                            <strong>• {typeof pt === 'object' ? (pt.point || pt.title || JSON.stringify(pt)) : pt}</strong>
                                                            {typeof pt === 'object' && pt.evidence && (
                                                                <div style={{ fontSize: '0.72rem', color: 'var(--muted)', marginTop: '0.15rem' }}>
                                                                    <em>Evidence:</em> {pt.evidence}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>N/A</span>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem' }}>
                                            <span className={`status-badge ${lead.status}`}>
                                                {lead.status}
                                            </span>
                                            {lead.linkedin_url && (
                                                <div style={{ marginTop: '0.5rem' }}>
                                                    <a href={lead.linkedin_url} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none', fontSize: '0.8rem' }}>
                                                        LinkedIn
                                                    </a>
                                                </div>
                                            )}
                                        </td>
                                        <td style={{ padding: '1rem' }}>
                                            <button
                                                className="ui-button-secondary"
                                                style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.4rem 0.75rem', fontSize: '0.85rem' }}
                                                onClick={() => handleViewEmails(lead.id)}
                                            >
                                                <Mail size={14} />
                                                View Emails
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                )}
            </div>
        </div>
    );
};

export default LeadsTable;