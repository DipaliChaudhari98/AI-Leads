import React from 'react';
import { LayoutDashboard, CalendarDays, Inbox, Send, LogOut, Users } from 'lucide-react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Sidebar = () => {
    const { email, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <div className="logo">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                    </svg>
                    <span>LeadGen AI</span>
                </div>
            </div>
            <nav className="nav-menu">
                <NavLink to="/" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <LayoutDashboard size={20} />
                    Dashboard
                </NavLink>
                <NavLink to="/leads" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Users size={20} />
                    Leads Directory
                </NavLink>
                {/* <NavLink to="/emails" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Inbox size={20} />
                    Emails
                </NavLink> */}
                <NavLink to="/followups" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Send size={20} />
                    Manual Review
                </NavLink>
                <NavLink to="/followup-dates" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <CalendarDays size={20} />
                    Follow-up Dates
                </NavLink>
                <NavLink to="/campaigns" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                    <Inbox size={20} />
                    Campaigns
                </NavLink>
            </nav>
            <div className="sidebar-footer">
                <div className="user-email">{email}</div>
                <button onClick={handleLogout} className="nav-item logout-btn">
                    <LogOut size={20} />
                    Sign Out
                </button>
            </div>
        </aside>
    );
};

export default Sidebar;
