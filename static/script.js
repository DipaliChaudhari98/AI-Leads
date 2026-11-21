document.addEventListener('DOMContentLoaded', () => {
    const campaignForm = document.getElementById('campaign-form');
    const submitBtn = document.getElementById('submit-btn');
    const loader = document.getElementById('loader');
    const leadsContainer = document.getElementById('leads-container');
    const refreshBtn = document.getElementById('refresh-btn');
    const campaignStatusMsg = document.getElementById('campaign-status-msg');
    const campaignStatusText = document.getElementById('campaign-status-text');
    const controlPanel = document.getElementById('control-panel');
    const submitText = document.getElementById('submit-text');

    // Stats elements
    const statTotal = document.getElementById('stat-total');
    const statSent = document.getElementById('stat-sent');
    const statQualified = document.getElementById('stat-qualified');

    let isPolling = false;

    // Fetch leads and stats
    // Fetch all three data sources in parallel
    const fetchData = async () => {
        try {
            const [leadsRes, statsRes, followRes] = await Promise.all([
                fetch('/api/leads'),
                fetch('/api/stats'),
                fetch('/api/follow_ups')
            ]);

            const leads = await leadsRes.json();
            const stats = await statsRes.json();
            const followups = await followRes.json();

            // Use the data
            updateStats(stats);
            renderLeads(leads);
            renderFollowups(followups);
            renderFollowupDates(leads);

        } catch (error) {
            console.error('Error fetching data:', error);
        }
    };

    const updateStats = (stats) => {
        statTotal.textContent = stats.total_leads || 0;
        statSent.textContent = stats.initial_emails_sent || 0;
        statQualified.textContent = (stats.statuses && stats.statuses.QUALIFIED) || 0;
    };

    const renderLeads = (leads) => {
        if (!leads || leads.length === 0) {
            leadsContainer.innerHTML = `
                <div class="empty-state">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="text-muted"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                    <p>No leads found.</p>
                    <span class="text-muted text-sm">Launch a campaign to start prospecting.</span>
                </div>
            `;
            return;
        }

        leadsContainer.innerHTML = leads.map(lead => {
            const initialDate = lead.initial_email_date ? new Date(lead.initial_email_date).toLocaleDateString() : 'N/A';
            const nextDate = lead.next_followup_date ? new Date(lead.next_followup_date).toLocaleDateString() : 'N/A';
            const lastDate = lead.last_followup_date ? new Date(lead.last_followup_date).toLocaleDateString() : 'N/A';
            
            return `
            <div class="lead-item">
                <div class="lead-info-group">
                    <div class="lead-avatar">${lead.name.charAt(0)}</div>
                    <div class="lead-details">
                        <h3>${lead.name}</h3>
                        <p>${lead.title} @ ${lead.company}</p>
                        <p style="font-size: 0.7rem; color: var(--muted-foreground); margin-top: 0.25rem;">
                            ${lead.email} • Via ${lead.source}
                        </p>
                        <div style="font-size: 0.75rem; margin-top: 0.5rem; display: flex; flex-wrap: wrap; gap: 1rem; color: var(--muted-foreground);">
                            <div><strong>Initial Email:</strong> ${initialDate} <span class="status-badge status-${(lead.initial_email_status || 'pending').toLowerCase()}" style="font-size: 0.6rem; padding: 0.1rem 0.3rem;">${lead.initial_email_status || 'Pending'}</span></div>
                            <div><strong>Last Follow-up:</strong> ${lastDate} <span class="status-badge status-${(lead.last_followup_status || 'n/a').toLowerCase()}" style="font-size: 0.6rem; padding: 0.1rem 0.3rem;">${lead.last_followup_status || 'N/A'}</span></div>
                            <div><strong>Next Follow-up:</strong> ${nextDate} <span class="status-badge status-${(lead.next_followup_status || 'n/a').toLowerCase()}" style="font-size: 0.6rem; padding: 0.1rem 0.3rem;">${lead.next_followup_status || 'N/A'}</span></div>
                        </div>
                    </div>
                </div>
                <div class="lead-actions">
                    <span class="status-badge status-${lead.status.toLowerCase()}">${lead.status.replace('_', ' ')}</span>
                </div>
            </div>
        `}).join('');

        // Attach event listeners for date inputs
        const dateInputs = leadsContainer.querySelectorAll('.initial-date-input');
        dateInputs.forEach(input => {
            input.addEventListener('change', async (e) => {
                const leadId = e.target.getAttribute('data-id');
                const newDate = e.target.value;
                if (!newDate) return;
                
                try {
                    const response = await fetch(`/api/leads/${leadId}/initial-date`, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ initial_date: newDate })
                    });
                    
                    if (response.ok) {
                        // Refresh to show recalculated follow-up dates
                        fetchData();
                    } else {
                        console.error('Failed to update date');
                        alert('Failed to update date');
                    }
                } catch (err) {
                    console.error(err);
                }
            });
        });
    };

    const checkCampaignStatus = async () => {
        try {
            const res = await fetch('/api/campaign-status');
            const status = await res.json();

            if (status.is_running) {
                isPolling = true;
                submitBtn.disabled = true;
                loader.style.display = 'block';
                submitText.textContent = 'Working...';

                campaignStatusMsg.style.display = 'flex';
                campaignStatusText.textContent = `Crew Status: ${status.current_step}`;

                // Fetch data periodically while running
                fetchData();
                setTimeout(checkCampaignStatus, 2000);
            } else {
                if (isPolling) {
                    // Just finished
                    fetchData();
                    isPolling = false;
                }
                submitBtn.disabled = false;
                loader.style.display = 'none';
                submitText.textContent = 'Launch Crew';
                campaignStatusMsg.style.display = 'none';
            }
        } catch (error) {
            console.error('Error checking status:', error);
        }
    };

    // View switching
    const navDashboard = document.getElementById('nav-dashboard');
    const navFollowups = document.getElementById('nav-followups');
    const navFollowupDates = document.getElementById('nav-followup-dates');
    const viewDashboard = document.getElementById('view-dashboard');
    const viewFollowups = document.getElementById('view-followups');
    const viewFollowupDates = document.getElementById('view-followup-dates');
    const followupsTbody = document.getElementById('followups-tbody');
    const selectAllCheckbox = document.getElementById('select-all-followups');

    const switchView = (viewToShow, navToActivate) => {
        [viewDashboard, viewFollowups, viewFollowupDates].forEach(v => {
            if (v) v.style.display = 'none';
        });
        [navDashboard, navFollowups, navFollowupDates].forEach(n => {
            if (n) n.classList.remove('active');
        });
        if (viewToShow) viewToShow.style.display = 'block';
        if (navToActivate) navToActivate.classList.add('active');
    };

    navDashboard.addEventListener('click', (e) => {
        e.preventDefault();
        switchView(viewDashboard, navDashboard);
    });
    
    navFollowups.addEventListener('click', async (e) => {
        e.preventDefault();
        switchView(viewFollowups, navFollowups);

        // Fetch fresh followups data when tab is clicked
        try {
            const res = await fetch('/api/follow_ups');
            const followups = await res.json();
            renderFollowups(followups);
        } catch (error) {
            console.error('Error loading followups:', error);
        }
    });

    navFollowupDates.addEventListener('click', (e) => {
        e.preventDefault();
        switchView(viewFollowupDates, navFollowupDates);
        fetchData(); // Ensure leads data is fresh for dates
    });



    // Select all logic
    selectAllCheckbox.addEventListener('change', (e) => {
        const checkboxes = document.querySelectorAll('.followup-checkbox');
        checkboxes.forEach(cb => cb.checked = e.target.checked);
    });
    // const renderFollowups = (followups) => {

    //     console.log(followups);
    //     if (!followups || !Array.isArray(followups) || followups.length ) {

    //         alert("Done");
    //         console.log("Done");
    //         followupsTbody.innerHTML = `
    //         <tr>
    //             <td colspan="7">
    //                 <div class="empty-state" style="padding: 3rem 1rem; background: transparent; border: none;">
    //                     <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="text-muted"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
    //                     <p style="margin-top: 1rem;">No follow-ups found.</p>

    const renderFollowups = (followups) => {

        console.log(followups);
        const data = Array.isArray(followups) ? followups : [];

        if (data.length === 0) {
            followupsTbody.innerHTML = `
            <tr>
                <td colspan="7">
                    <div class="empty-state" style="padding: 3rem 1rem; background: transparent; border: none;">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="text-muted"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
                        <p style="margin-top: 1rem;">No follow-ups found.</p>
                        <span class="text-muted text-sm">Your scheduled outreach will appear here.</span>
                    </div>
                </td>
            </tr>
        `;
            return;
        }

        followupsTbody.innerHTML = data.map(f => {
            console.log(data);

            const leadInitial = (f.lead_name || '?').charAt(0);
            const nextAction = f.next_followup_date
                ? new Date(f.next_followup_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                : 'Not Scheduled';
            const sentAt = f.sent_at
                ? new Date(f.sent_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
                : '';

            return `
            <tr>
                <td style="text-align: center; vertical-align: middle;">
                    <input type="checkbox" class="followup-checkbox ui-checkbox" value="${f.email_id}">
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <div class="lead-avatar" style="width: 32px; height: 32px; font-size: 0.8rem;">
                            ${leadInitial}
                        </div>
                        <div>
                            <div style="font-weight: 600; font-size: 0.9rem;">${f.lead_name || '-'}</div>
                            <div class="text-muted text-sm" style="margin-top: 0.1rem;">${f.company || '-'}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="color: var(--foreground);">${f.email || '-'}</div>
                    <div class="text-muted" style="font-size: 0.75rem; margin-top: 0.25rem;">
                        ${f.followup_count > 0 ? `Sent ${f.followup_count} emails` : 'No emails sent yet'}
                    </div>
                </td>
                <td>
                    <div style="font-weight: 500;">${(f.followup_type || '-').replace(/_/g, ' ')}</div>
                    ${sentAt ? `<div class="text-muted" style="font-size: 0.75rem; margin-top: 0.25rem;">Sent: ${sentAt}</div>` : ''}
                </td>
                <td>
                    <span class="status-badge status-${(f.status || '').toLowerCase()}">
                        ${(f.status || '-').replace(/_/g, ' ')}
                    </span>
                </td>
                <td>
                    <span class="status-badge status-${(f.lead_status || '').toLowerCase()}">
                        ${(f.lead_status || '-').replace(/_/g, ' ')}
                    </span>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        ${nextAction}
                    </div>
                </td>
            </tr>
        `}).join('');
    };

    const renderFollowupDates = (leads) => {
        const tbody = document.getElementById('followup-dates-tbody');
        if (!tbody) return;

        if (!leads || leads.length === 0) {
            tbody.innerHTML = `
            <tr>
                <td colspan="4">
                    <div class="empty-state" style="padding: 3rem 1rem; background: transparent; border: none;">
                        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" class="text-muted"><path d="M22 12h-4l-3 9L9 3l-3 9H2"></path></svg>
                        <p style="margin-top: 1rem;">No leads found.</p>
                        <span class="text-muted text-sm">Launch a campaign to see follow-up dates here.</span>
                    </div>
                </td>
            </tr>
            `;
            return;
        }

        tbody.innerHTML = leads.map(lead => {
            const initialDateVal = lead.initial_email_date ? lead.initial_email_date.split('T')[0] : '';
            const nextDate = lead.next_followup_date ? new Date(lead.next_followup_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Not Scheduled';
            const lastDate = lead.last_followup_date ? new Date(lead.last_followup_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }) : 'Not Scheduled';
            const leadInitial = (lead.name || '?').charAt(0);
            
            return `
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <div class="lead-avatar" style="width: 32px; height: 32px; font-size: 0.8rem;">
                            ${leadInitial}
                        </div>
                        <div>
                            <div style="font-weight: 600; font-size: 0.9rem;">${lead.name || '-'}</div>
                            <div class="text-muted text-sm" style="margin-top: 0.1rem;">${lead.title ? lead.title + ' @ ' : ''}${lead.company || '-'}</div>
                            <div class="text-muted text-sm" style="margin-top: 0.1rem; font-size: 0.7rem;">${lead.email || '-'}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <input type="date" class="initial-date-input ui-input" style="padding: 0.25rem 0.5rem; border-radius: 4px; font-family: inherit; font-size: 0.8rem; background: var(--card); border: 1px solid var(--border); color: var(--foreground);" data-id="${lead.id}" value="${initialDateVal}">
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: white;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="16" y1="2" x2="16" y2="6"></line>
                            <line x1="8" y1="2" x2="8" y2="6"></line>
                            <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                        ${nextDate}
                    </div>
                </td>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.875rem; color: white;">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-muted">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        ${lastDate}
                    </div>
                </td>
            </tr>
            `;
        }).join('');

        // Attach event listeners
        const dateInputs = tbody.querySelectorAll('.initial-date-input');
        dateInputs.forEach(input => {
            input.addEventListener('change', async (e) => {
                const leadId = e.target.getAttribute('data-id');
                const newDate = e.target.value;
                if (!newDate) return;
                
                try {
                    const response = await fetch(`/api/leads/${leadId}/initial-date`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ initial_date: newDate })
                    });
                    
                    if (response.ok) {
                        fetchData(); // Refresh UI
                    } else {
                        console.error('Failed to update date');
                        alert('Failed to update date');
                    }
                } catch (err) {
                    console.error(err);
                }
            });
        });
    };

    campaignForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(campaignForm);
        try {
            const res = await fetch('/api/start-campaign', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok) {
                alert('Campaign started successfully!');
                checkCampaignStatus();
            } else {
                alert('Error starting campaign: ' + data.error);
            }
        } catch (error) {
            console.error('Error:', error);
            alert('Failed to start campaign');
        }
    });

    refreshBtn.addEventListener('click', fetchData);

    const processSelectedBtn = document.getElementById('process-selected-btn');
    if (processSelectedBtn) {
        processSelectedBtn.addEventListener('click', async () => {
            const checkboxes = document.querySelectorAll('.followup-checkbox:checked');
            if (checkboxes.length === 0) {
                alert('Please select at least one follow-up');
                return;
            }

            const selectedIds = Array.from(checkboxes).map(cb => cb.value);

            try {
                const res = await fetch('/api/follow_ups/process', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email_ids: selectedIds })
                });

                if (res.ok) {
                    alert('Follow-ups processed successfully');
                    // Refresh the table
                    const freshData = await fetch('/api/follow_ups');
                    const followups = await freshData.json();
                    renderFollowups(followups);
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Failed to process follow-ups');
            }
        });
    }

    // Initial load
    fetchData();
});
