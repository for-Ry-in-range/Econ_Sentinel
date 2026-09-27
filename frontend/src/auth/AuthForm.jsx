/*
Showing the UI for the login page and handling form interections
between the user and AuthContext.jsx
*/

import { useState } from 'react';
import { useAuth } from './AuthContext.jsx';
import ErrorBanner from '../components/ErrorBanner.jsx';


const MODES = {
  SIGN_IN: 'signin',
  SIGN_UP: 'signup',
  CONFIRM: 'confirm',
};

export default function AuthForm() {
  const { signIn, signUp, confirmSignUp, resendConfirmationCode } = useAuth();
  const [mode, setMode] = useState(MODES.SIGN_IN);  // mode tracks if in sign-in, sign-up, or email verification
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const reset = (nextMode) => {
    setError('');
    setNotice('');
    setMode(nextMode);
  };

  const handleSignIn = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await signIn(email, password);
      // On success the AuthProvider sets the user and App swaps in the dashboard.
    } catch (err) {
      if (err.code === 'UserNotConfirmedException') {
        setNotice('Your account is not confirmed yet. Enter the code we emailed you.');
        setMode(MODES.CONFIRM);
      } else {
        setError(err.message || 'Sign in failed.');
      }
    } finally {
      setBusy(false);
    }
  };

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await signUp(email, password);
      setNotice('Account created. Check your email for a verification code.');
      setMode(MODES.CONFIRM);
    } catch (err) {
      setError(err.message || 'Sign up failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleConfirm = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await confirmSignUp(email, code);
      setNotice('Email verified. You can now sign in.');
      setCode('');
      setMode(MODES.SIGN_IN);
    } catch (err) {
      setError(err.message || 'Confirmation failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleResend = async () => {
    setError('');
    try {
      await resendConfirmationCode(email);
      setNotice('A new code has been sent to your email.');
    } catch (err) {
      setError(err.message || 'Could not resend code.');
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1 className="brand">Econ Sentinel</h1>
        <p className="tagline">Macroeconomic stress monitoring</p>
        {/* only render if user is not in confirmation: */}
        {mode !== MODES.CONFIRM && (
          <div className="auth-tabs">
            <button
              type="button"
              className={mode === MODES.SIGN_IN ? 'active' : ''}
              onClick={() => reset(MODES.SIGN_IN)}
            >
              Sign in
            </button>
            <button
              type="button"
              className={mode === MODES.SIGN_UP ? 'active' : ''}
              onClick={() => reset(MODES.SIGN_UP)}
            >
              Sign up
            </button>
          </div>
        )}

        {/*Show component only if value is true*/}
        {error && <ErrorBanner message={error} onDismiss={() => setError('')} />}
        {notice && <div className="notice">{notice}</div>}

        {mode === MODES.SIGN_IN && (
          <form onSubmit={handleSignIn}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
              />
            </label>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        )}

        {mode === MODES.SIGN_UP && (
          <form onSubmit={handleSignUp}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
            </label>
            <p className="hint">
              At least 8 characters, with an uppercase letter and a number.
            </p>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        )}

        {mode === MODES.CONFIRM && (
          <form onSubmit={handleConfirm}>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
              />
            </label>
            <label>
              Verification code
              <input
                type="text"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                inputMode="numeric"
              />
            </label>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Verifying…' : 'Verify email'}
            </button>
            <div className="auth-links">
              <button type="button" className="link" onClick={handleResend}>
                Resend code
              </button>
              <button type="button" className="link" onClick={() => reset(MODES.SIGN_IN)}>
                Back to sign in
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
