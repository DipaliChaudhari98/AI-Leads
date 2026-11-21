import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => useContext(AuthContext);

export const AuthProvider = ({ children }) => {
    const [token, setToken] = useState(localStorage.getItem('token') || null);
    const [email, setEmail] = useState(localStorage.getItem('email') || null);

    const login = (newToken, userEmail) => {
        localStorage.setItem('token', newToken);
        localStorage.setItem('email', userEmail);
        setToken(newToken);
        setEmail(userEmail);
    };

    const logout = () => {
        localStorage.removeItem('token');
        localStorage.removeItem('email');
        setToken(null);
        setEmail(null);
    };

    return (
        <AuthContext.Provider value={{ token, email, login, logout, isAuthenticated: !!token }}>
            {children}
        </AuthContext.Provider>
    );
};
