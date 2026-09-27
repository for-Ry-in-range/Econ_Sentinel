/*
Manages authentication using Cognito and shares the state globally
*/

import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import * as cognito from './cognito.js';


const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // { email, sub, idToken } | null
  const [loading, setLoading] = useState(true);

  // Restore existing session when page first loads
  useEffect(() => {
    let active = true;
    cognito
      .getCurrentUser()
      .then((u) => {
        if (active) setUser(u);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;  // when the component finishes
    };
  }, []);

  const signIn = useCallback(async (email, password) => {
    const u = await cognito.signIn(email, password);
    setUser(u);
    return u;
  }, []);

  const signOut = useCallback(() => {
    cognito.signOut();
    setUser(null);
  }, []);

  /**
   * Get signed-in user. If not signed in, user gets redirected to login page
   */
  const getIdToken = useCallback(async () => {
    const u = await cognito.getCurrentUser();
    if (!u) {
      setUser(null);
      return null;
    }
    setUser(u);
    return u.idToken;
  }, []);

  const value = {
    user,
    loading,
    isAuthenticated: Boolean(user),
    signIn,
    signOut,
    getIdToken,
    signUp: cognito.signUp,
    confirmSignUp: cognito.confirmSignUp,
    resendConfirmationCode: cognito.resendConfirmationCode,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
