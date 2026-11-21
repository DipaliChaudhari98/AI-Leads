import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Mail, Lock, User, ArrowRight, Activity } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

const AuthBackground = () => (
    <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 0, overflow: 'hidden', background: '#0a0a0f' }}>
        <div style={{ position: 'absolute', top: '-10%', left: '-10%', width: '50vw', height: '50vw', background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, rgba(0,0,0,0) 70%)', filter: 'blur(60px)', animation: 'float 10s ease-in-out infinite' }} />
        <div style={{ position: 'absolute', bottom: '-10%', right: '-10%', width: '60vw', height: '60vw', background: 'radial-gradient(circle, rgba(168,85,247,0.15) 0%, rgba(0,0,0,0) 70%)', filter: 'blur(60px)', animation: 'float 12s ease-in-out infinite reverse' }} />
        
        <style>
            {`
            @keyframes float {
                0% { transform: translate(0, 0) scale(1); }
                33% { transform: translate(30px, -50px) scale(1.1); }
                66% { transform: translate(-20px, 20px) scale(0.9); }
                100% { transform: translate(0, 0) scale(1); }
            }
            .glass-panel {
                background: rgba(17, 17, 24, 0.7);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                border-radius: 16px;
            }
            .input-wrapper {
                position: relative;
                display: flex;
                align-items: center;
                transition: all 0.3s ease;
            }
            .input-wrapper:focus-within {
                transform: translateY(-2px);
            }
            .auth-icon {
                position: absolute;
                left: 14px;
                color: var(--muted-foreground);
                transition: color 0.3s ease;
            }
            .input-wrapper:focus-within .auth-icon {
                color: var(--primary);
            }
            .premium-input {
                width: 100%;
                padding: 12px 16px 12px 42px;
                background: rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 10px;
                color: white;
                font-size: 0.95rem;
                transition: all 0.3s ease;
            }
            .premium-input:focus {
                outline: none;
                border-color: rgba(99, 102, 241, 0.5);
                background: rgba(0, 0, 0, 0.3);
                box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
            }
            .premium-btn {
                background: linear-gradient(135deg, var(--primary) 0%, #818cf8 100%);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 14px;
                font-weight: 600;
                font-size: 1rem;
                cursor: pointer;
                transition: all 0.3s ease;
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 8px;
            }
            .premium-btn:hover:not(:disabled) {
                transform: translateY(-2px);
                box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.4);
            }
            .premium-btn:disabled {
                opacity: 0.7;
                cursor: not-allowed;
            }
            `}
        </style>
    </div>
);

export function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await fetch(`/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Login failed');
            }
            
            login(data.access_token, data.email);
            navigate('/');
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', position: 'relative' }}>
            <AuthBackground />
            
            <div className="glass-panel fade-in" style={{ padding: '3rem 2.5rem', width: '100%', maxWidth: '420px', position: 'relative', zIndex: 1, margin: '2rem' }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
                    <div style={{ background: 'rgba(99,102,241,0.2)', padding: '12px', borderRadius: '14px', border: '1px solid rgba(99,102,241,0.3)' }}>
                        <Activity size={32} color="#818cf8" />
                    </div>
                </div>
                
                <h2 style={{ textAlign: 'center', marginBottom: '0.5rem', color: 'white', fontSize: '1.75rem', fontWeight: '600', letterSpacing: '-0.02em' }}>Welcome Back</h2>
                <p style={{ textAlign: 'center', marginBottom: '2.5rem', color: 'var(--muted-foreground)', fontSize: '0.95rem' }}>Sign in to access your dashboard</p>
                
                {error && (
                    <div className="fade-in" style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', borderRadius: '10px', marginBottom: '1.5rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '4px', height: '16px', background: '#ef4444', borderRadius: '2px' }} />
                        {error}
                    </div>
                )}
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="form-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>Email Address</label>
                        <div className="input-wrapper">
                            <Mail size={18} className="auth-icon" />
                            <input
                                type="email"
                                className="premium-input"
                                placeholder="name@abc.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <div className="form-group">
                        <label style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>
                            <span>Password</span>
                        </label>
                        <div className="input-wrapper">
                            <Lock size={18} className="auth-icon" />
                            <input
                                type="password"
                                className="premium-input"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <button type="submit" className="premium-btn" disabled={loading} style={{ marginTop: '0.5rem' }}>
                        {loading ? 'Authenticating...' : 'Sign In'}
                        {!loading && <ArrowRight size={18} />}
                    </button>
                </form>
                
                <p style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.9rem', color: 'var(--muted-foreground)' }}>
                    Don't have an account? <Link to="/register" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: '500', transition: 'color 0.2s' }}>Create one</Link>
                </p>
            </div>
        </div>
    );
}

export function Register() {
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState('');
    const [success, setSuccess] = useState('');
    const [loading, setLoading] = useState(false);
    
    const { login } = useAuth();
    const navigate = useNavigate();
    
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setSuccess('');

        if (password !== confirmPassword) {
            setError('Passwords do not match');
            return;
        }

        setLoading(true);

        try {
            const response = await fetch(`/api/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password, confirm_password: confirmPassword })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Registration failed');
            }
            
            if (data.access_token) {
                login(data.access_token, data.email);
                navigate('/');
            } else {
                setSuccess('Registration successful! You can now sign in.');
                setName('');
                setEmail('');
                setPassword('');
                setConfirmPassword('');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', position: 'relative', padding: '2rem 0' }}>
            <AuthBackground />
            
            <div className="glass-panel fade-in" style={{ padding: '2.5rem', width: '100%', maxWidth: '420px', position: 'relative', zIndex: 1, margin: 'auto' }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
                    <div style={{ background: 'rgba(99,102,241,0.2)', padding: '12px', borderRadius: '14px', border: '1px solid rgba(99,102,241,0.3)' }}>
                        <User size={32} color="#818cf8" />
                    </div>
                </div>
                
                <h2 style={{ textAlign: 'center', marginBottom: '0.5rem', color: 'white', fontSize: '1.75rem', fontWeight: '600', letterSpacing: '-0.02em' }}>Create Account</h2>
                <p style={{ textAlign: 'center', marginBottom: '2rem', color: 'var(--muted-foreground)', fontSize: '0.95rem' }}>Only @abc.com emails are permitted</p>
                
                {error && (
                    <div className="fade-in" style={{ padding: '1rem', background: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)', color: '#fca5a5', borderRadius: '10px', marginBottom: '1.5rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '4px', height: '16px', background: '#ef4444', borderRadius: '2px' }} />
                        {error}
                    </div>
                )}
                
                {success && (
                    <div className="fade-in" style={{ padding: '1rem', background: 'rgba(34, 197, 94, 0.15)', border: '1px solid rgba(34, 197, 94, 0.3)', color: '#86efac', borderRadius: '10px', marginBottom: '1.5rem', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '4px', height: '16px', background: '#22c55e', borderRadius: '2px' }} />
                        {success}
                    </div>
                )}
                
                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                    <div className="form-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>Full Name</label>
                        <div className="input-wrapper">
                            <User size={18} className="auth-icon" />
                            <input
                                type="text"
                                className="premium-input"
                                placeholder="John Doe"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <div className="form-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>Email Address</label>
                        <div className="input-wrapper">
                            <Mail size={18} className="auth-icon" />
                            <input
                                type="email"
                                className="premium-input"
                                placeholder="name@abc.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <div className="form-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>Password</label>
                        <div className="input-wrapper">
                            <Lock size={18} className="auth-icon" />
                            <input
                                type="password"
                                className="premium-input"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <div className="form-group">
                        <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.85rem', fontWeight: '500', color: 'rgba(255,255,255,0.8)' }}>Confirm Password</label>
                        <div className="input-wrapper">
                            <Lock size={18} className="auth-icon" />
                            <input
                                type="password"
                                className="premium-input"
                                placeholder="••••••••"
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                required
                            />
                        </div>
                    </div>
                    
                    <button type="submit" className="premium-btn" disabled={loading} style={{ marginTop: '0.5rem' }}>
                        {loading ? 'Creating Account...' : 'Register'}
                        {!loading && <ArrowRight size={18} />}
                    </button>
                </form>
                
                <p style={{ textAlign: 'center', marginTop: '2rem', fontSize: '0.9rem', color: 'var(--muted-foreground)' }}>
                    Already have an account? <Link to="/login" style={{ color: '#818cf8', textDecoration: 'none', fontWeight: '500' }}>Sign in</Link>
                </p>
            </div>
        </div>
    );
}
