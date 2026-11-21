import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Followups from './components/Followups';
import FollowupDates from './components/FollowupDates';
import Emails from './components/Emails';
import LeadsTable from './components/LeadsTable';
import { Login, Register } from './components/Login';
import { useAuth } from './context/AuthContext';

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function App() {
  const { isAuthenticated } = useAuth();
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);

  // Maintain AbortController ref to cancel pending /api/stats requests on unmount or re-fetch
  const statsAbortRef = React.useRef(null);
  // Guard flag to prevent overlapping concurrent calls to /api/stats from App component
  const isFetchingStatsRef = React.useRef(false);

  const fetchData = async () => {
    if (!isAuthenticated) return;
    
    // Deduplication check: if a stats request is already pending, don't stack another duplicate
    if (isFetchingStatsRef.current) {
      return;
    }

    // Cancel any previous stale in-flight request
    if (statsAbortRef.current) {
      statsAbortRef.current.abort();
    }
    statsAbortRef.current = new AbortController();
    isFetchingStatsRef.current = true;

    try {
      // Pass signal for request cancellation and 8s timeout to prevent hanging connections
      const statsRes = await axios.get('/api/stats', {
        signal: statsAbortRef.current.signal,
        timeout: 8000
      });
      setStats(statsRes.data);
    } catch (err) {
      // Ignore errors caused by intentional AbortController cancellation
      if (!axios.isCancel(err) && err.name !== 'CanceledError') {
        console.error('Failed to fetch stats:', err);
      }
    } finally {
      isFetchingStatsRef.current = false;
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      fetchData();
    } else {
      setLoading(false);
    }

    // Cleanup hook: abort active in-flight requests when component unmounts or auth state changes
    return () => {
      if (statsAbortRef.current) {
        statsAbortRef.current.abort();
      }
    };
  }, [isAuthenticated]);

  if (loading) {
    return (
      <div style={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', color: 'white' }}>
        <div className="loader"></div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={!isAuthenticated ? <Login /> : <Navigate to="/" replace />} />
        <Route path="/register" element={!isAuthenticated ? <Register /> : <Navigate to="/" replace />} />
        
        <Route path="/*" element={
          <ProtectedRoute>
            <div className="app-container">
              <Sidebar />
              <main className="main-content">
                <Routes>
                  <Route path="/" element={<Dashboard stats={stats} fetchData={fetchData} />} />
                  <Route path="/leads" element={<LeadsTable />} />
                  <Route path="/emails" element={<Emails />} />
                  <Route path="/followups" element={<Followups />} />
                  <Route path="/followup-dates" element={<FollowupDates />} />
                  <Route path="/campaigns" element={
                    <div className="fade-in" style={{ color: 'white' }}>
                      <h2>Campaigns</h2>
                      <p className="text-muted">Campaign management coming soon...</p>
                    </div>
                  } />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
              </main>
            </div>
          </ProtectedRoute>
        } />
      </Routes>
    </Router>
  );
}

export default App;
