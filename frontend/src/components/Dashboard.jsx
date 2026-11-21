import React, { useState, useEffect } from 'react';
import axios from 'axios';

const Dashboard = ({ stats, fetchData }) => {
    const [leads, setLeads] = useState([]);
    const [page, setPage] = useState(1);
    const [total, setTotal] = useState(0);
    const limit = 50;

    // AbortController ref for canceling stale in-flight /api/leads requests on page switch or unmount
    const leadsAbortRef = React.useRef(null);
    // Lock ref to prevent initiating duplicate overlapping /api/leads requests
    const isFetchingLeadsRef = React.useRef(false);

    // Ref to track and clean up active campaign status interval timer on component unmount
    const pollIntervalRef = React.useRef(null);
    // Lock ref to prevent polling tick from triggering new requests if previous tick is still in-flight
    const isPollCycleInFlightRef = React.useRef(false);

    const fetchLeads = async () => {
        // Prevent duplicate concurrent requests to /api/leads
        if (isFetchingLeadsRef.current) return;

        // Cancel previous stale request if page changed before it completed
        if (leadsAbortRef.current) {
            leadsAbortRef.current.abort();
        }
        leadsAbortRef.current = new AbortController();
        isFetchingLeadsRef.current = true;

        try {
            // Pass signal and 8s timeout to prevent requests from hanging in (pending) state forever
            const res = await axios.get(`/api/leads?page=${page}&limit=${limit}`, {
                signal: leadsAbortRef.current.signal,
                timeout: 8000
            });
            setLeads(res.data.data);
            setTotal(res.data.total);
        } catch (err) {
            // Ignore intentional cancellation errors
            if (!axios.isCancel(err) && err.name !== 'CanceledError') {
                console.error('Failed to fetch leads:', err);
            }
        } finally {
            isFetchingLeadsRef.current = false;
        }
    };

    useEffect(() => {
        fetchLeads();

        // Cleanup hook: cancel any pending leads fetch and clear polling interval when component unmounts
        return () => {
            if (leadsAbortRef.current) {
                leadsAbortRef.current.abort();
            }
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
            }
        };
    }, [page]);

    const [isRunning, setIsRunning] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    // Form state
    const [formData, setFormData] = useState({
        roles: 'CEO, Founder',
        location: '',
        industry: 'Software',
        companies: '',
        size: '',
        limit: 10,
        filters: '',
        strategy: 'fixed',
        mode: 'agent'
    });

    const handleChange = (e) => {
        setFormData({
            ...formData,
            [e.target.name]: e.target.value
        });
    };

    const handleReset = () => {
        setFormData({
            roles: '',
            location: '',
            industry: '',
            companies: '',
            size: '',
            limit: 10,
            filters: '',
            strategy: 'fixed',
            mode: 'agent'
        });
    };

    const launchCampaign = async (e) => {
        e.preventDefault();
        setIsRunning(true);
        setStatusMessage('Crew is working...');

        // Clear any pre-existing interval before starting a new one
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
        }

        try {
            const data = new FormData();
            for (const key in formData) {
                data.append(key, formData[key]);
            }

            await axios.post('/api/start-campaign', data, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            // Start status polling with deduplication guard to prevent piling up 120+ pending requests
            pollIntervalRef.current = setInterval(async () => {
                // If previous polling tick is still executing/pending, skip this interval tick to prevent request stacking
                if (isPollCycleInFlightRef.current) return;
                isPollCycleInFlightRef.current = true;

                try {
                    const statusRes = await axios.get('/api/campaign-status', { timeout: 8000 });
                    if (statusRes.data.is_running) {
                        setStatusMessage(`Crew Status: ${statusRes.data.current_step}`);
                        await Promise.allSettled([
                            fetchData(),
                            fetchLeads()
                        ]);
                    } else {
                        if (pollIntervalRef.current) {
                            clearInterval(pollIntervalRef.current);
                            pollIntervalRef.current = null;
                        }
                        setIsRunning(false);
                        setStatusMessage('');
                        await Promise.allSettled([
                            fetchData(),
                            fetchLeads()
                        ]);
                        alert('Campaign completed successfully!');
                    }
                } catch (err) {
                    if (!axios.isCancel(err) && err.name !== 'CanceledError') {
                        console.error('Status check error:', err);
                    }
                } finally {
                    isPollCycleInFlightRef.current = false;
                }
            }, 2000);

        } catch (err) {
            console.error('Error starting campaign:', err);
            setIsRunning(false);
            alert('Failed to start campaign: ' + (err.response?.data?.error || err.message));
        }
    };
    const locations = [
        "India",
        "France",
        "United Kingdom",
        "Australia",
        "Canada",
        "Germany"
    ];
    return (
        <div className="fade-in">
            <div className="dashboard-layout" style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
                {/* Left Column: Form */}
                <div className="ui-card" id="control-panel">
                    <div className="card-header">
                        <h2>New Campaign</h2>
                        <p className="text-muted">Configure the parameters for the agents to start prospecting.</p>
                    </div>

                    <form id="campaign-form" className="space-y-6" onSubmit={launchCampaign}>
                        <div className="form-group">
                            <label htmlFor="roles">Target Roles</label>
                            <input type="text" id="roles" name="roles" className="ui-input"
                                placeholder="e.g. CTO, VP Engineering" required value={formData.roles} onChange={handleChange} />
                            <p className="form-help">The job titles you want to target.</p>
                        </div>

                        <div className="form-row" style={{ display: 'flex', gap: '1rem' }}>
                            <div className="form-group flex-1">
                                <label htmlFor="location">Target Location</label>
                                <select
                                    id="location"
                                    name="location"
                                    className="ui-select"
                                    value={formData.location}
                                    onChange={handleChange}
                                    style={{
                                        width: "100%",
                                        padding: "0.5rem",
                                        background: "var(--background)",
                                        color: "var(--foreground)",
                                        border: "1px solid var(--border)",
                                        borderRadius: "4px"
                                    }}
                                >
                                    <option value="">Select Location</option>

                                    {locations.map((location) => (
                                        <option key={location} value={location}>
                                            {location}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-group flex-1">
                                <label htmlFor="industry">Target Industry</label>
                                <input type="text" id="industry" name="industry" className="ui-input"
                                    placeholder="e.g. Software" value={formData.industry} onChange={handleChange} />
                            </div>
                        </div>

                        <div className="dashed-section space-y-4" style={{ borderTop: '1px dashed var(--border)', paddingTop: '1rem', marginTop: '1rem' }}>
                            <div className="form-group">
                                <label htmlFor="companies">Seed Companies (Optional)</label>
                                <input type="text" id="companies" name="companies" className="ui-input"
                                    placeholder="e.g. Google, Microsoft" value={formData.companies} onChange={handleChange} />
                                <p className="form-help">Specific companies to bypass general industry search.</p>
                            </div>
                            
                            <div className="form-row" style={{ display: 'flex', gap: '1rem' }}>
                                <div className="form-group flex-1">
                                    <label htmlFor="size">Company Size</label>
                                    <input type="text" id="size" name="size" className="ui-input"
                                        placeholder="e.g. 51-200" value={formData.size} onChange={handleChange} />
                                </div>
                                <div className="form-group flex-1">
                                    <label htmlFor="limit">Total Results</label>
                                    <input type="number" id="limit" name="limit" className="ui-input"
                                        min="1" max="100" value={formData.limit} onChange={handleChange} />
                                </div>
                            </div>
                            
                            <div className="form-group" style={{ marginTop: '1rem' }}>
                                <label htmlFor="filters">Custom Filters (JSON or key=value)</label>
                                <input type="text" id="filters" name="filters" className="ui-input"
                                    placeholder='e.g. {"hasEmail": true} or hasEmail=true' value={formData.filters} onChange={handleChange} />
                                <p className="form-help">Additional scraper parameters.</p>
                            </div>
                        </div>

                        <div className="form-group" style={{ marginTop: '1rem' }}>
                            <label htmlFor="strategy">Follow-up Strategy</label>
                            <select id="strategy" name="strategy" className="ui-select" value={formData.strategy} onChange={handleChange} style={{ width: '100%', padding: '0.5rem', background: 'var(--background)', color: 'var(--foreground)', border: '1px solid var(--border)', borderRadius: '4px' }}>
                                <option value="fixed">Fixed (Send regardless)</option>
                            </select>
                        </div>

                        <input type="hidden" name="mode" value="agent" />

                        <div className="form-actions" style={{ display: 'flex', gap: '1rem', marginTop: '1.5rem' }}>
                            <button type="button" className="btn btn-outline" onClick={handleReset} disabled={isRunning}>Reset</button>
                            <button type="submit" className="btn btn-primary" id="submit-btn" disabled={isRunning} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                {isRunning ? 'Working...' : 'Launch Crew'}
                                {isRunning && <div className="loader" style={{ width: '16px', height: '16px' }}></div>}
                            </button>
                        </div>
                    </form>

                    {isRunning && (
                        <div id="campaign-status-msg" className="status-alert" style={{ marginTop: '1rem', padding: '1rem', background: 'var(--primary-light)', borderRadius: '4px', border: '1px solid var(--primary)' }}>
                            <span id="campaign-status-text" style={{ color: 'var(--primary)' }}>{statusMessage}</span>
                        </div>
                    )}
                </div>

                {/* Right Column: Stats & Leads */}
                <div className="space-y-6" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    <div className="stats-container" style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
                        <div className="ui-stat-card stat-card" style={{ padding: '1.5rem', background: 'var(--card)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                            <div className="stat-header">
                                <span className="stat-title text-muted">Total Leads</span>
                            </div>
                            <div className="stat-value" style={{ fontSize: '2rem', fontWeight: 'bold' }}>{stats.total_leads || 0}</div>
                        </div>
                        <div className="ui-stat-card stat-card" style={{ padding: '1.5rem', background: 'var(--card)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                            <div className="stat-header">
                                <span className="stat-title text-muted">Emails Sent</span>
                            </div>
                            <div className="stat-value" style={{ fontSize: '2rem', fontWeight: 'bold' }}>{stats.initial_emails_sent || 0}</div>
                        </div>
                        <div className="ui-stat-card stat-card" style={{ padding: '1.5rem', background: 'var(--card)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                            <div className="stat-header">
                                <span className="stat-title text-muted">Qualified Leads</span>
                            </div>
                            <div className="stat-value" style={{ fontSize: '2rem', fontWeight: 'bold' }}>{stats.statuses?.QUALIFIED || 0}</div>
                        </div>
                    </div>

                    <div className="ui-card flex-1" style={{ display: 'flex', flexDirection: 'column' }}>
                        <div className="card-header">
                            <h2>Live CRM Feed</h2>
                            <p className="text-muted">Real-time updates from your automated agents.</p>
                        </div>
                        <div className="leads-feed">
                            {!leads || leads.length === 0 ? (
                                <div className="empty-state">
                                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" className="text-muted">
                                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                                        <circle cx="12" cy="7" r="4"></circle>
                                    </svg>
                                    <p>No leads found.</p>
                                    <span className="text-muted text-sm">Launch a campaign to start prospecting.</span>
                                </div>
                            ) : (
                                leads.map(lead => {
                                    const initialDate = lead.initial_email_date || 'N/A';
                                    const nextDate = lead.next_followup_date || 'N/A';
                                    const lastDate = lead.last_followup_date || 'N/A';
                                    const painPoints = Array.isArray(lead.pain_points) ? lead.pain_points : [];

                                    return (
                                        <div className="lead-item" key={lead.id} style={{ padding: '1rem', borderBottom: '1px solid var(--border)' }}>
                                            <div className="lead-info-group" style={{ display: 'flex', gap: '1rem' }}>
                                                <div className="lead-avatar" style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'var(--primary)', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>{(lead.name || '?').charAt(0)}</div>
                                                <div className="lead-details" style={{ flex: 1 }}>
                                                    <h3 style={{ margin: 0 }}>{lead.name}</h3>
                                                    <p style={{ margin: '0.25rem 0 0 0' }}>{lead.title} @ {lead.company}</p>
                                                    <p style={{ fontSize: '0.7rem', color: 'var(--muted-foreground)', marginTop: '0.25rem' }}>
                                                        {lead.email} • Via {lead.source}
                                                    </p>
                                                    
                                                    {painPoints.length > 0 && (
                                                        <div style={{ marginTop: '0.5rem', background: 'var(--background)', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border)' }}>
                                                            <div style={{ fontSize: '0.75rem', fontWeight: 'bold', color: 'var(--foreground)' }}>Pain Points:</div>
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem', marginTop: '0.2rem' }}>
                                                                {painPoints.map((pt, idx) => (
                                                                    <div key={idx} style={{ fontSize: '0.72rem', color: 'var(--muted-foreground)' }}>
                                                                        • {typeof pt === 'object' ? (pt.point || pt.title || JSON.stringify(pt)) : pt}
                                                                        {typeof pt === 'object' && pt.evidence && <span> — <em>{pt.evidence}</em></span>}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    )}

                                                    <div style={{ fontSize: '0.75rem', marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '1rem', color: 'var(--muted-foreground)' }}>
                                                        <div><strong>Initial Email:</strong> {initialDate} <span className={`status-badge status-${(lead.initial_email_status || 'pending').toLowerCase()}`} style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>{lead.initial_email_status || 'Pending'}</span></div>
                                                        <div><strong>Last Follow-up:</strong> {lastDate} <span className={`status-badge status-${(lead.last_followup_status || 'n/a').toLowerCase()}`} style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>{lead.last_followup_status || 'Pending'}</span></div>
                                                        <div><strong>Next Follow-up:</strong> {nextDate} <span className={`status-badge status-${(lead.next_followup_status || 'n/a').toLowerCase()}`} style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>{lead.next_followup_status || 'Pending'}</span></div>
                                                    </div>
                                                </div>
                                            </div>
                                            <div className="lead-actions" style={{ marginTop: '1rem' }}>
                                                <span className={`status-badge status-${(lead.status || '').toLowerCase()}`}>{(lead.status || '').replace('_', ' ')}</span>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
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
            </div>
        </div>
    );
};

export default Dashboard;
