import { useAuth } from './auth/AuthContext.jsx';
import { isConfigured } from './config.js';
import AuthForm from './auth/AuthForm.jsx';
import Dashboard from './components/Dashboard.jsx';
import Loading from './components/Loading.jsx';

export default function App() {
  const { loading, isAuthenticated } = useAuth();

  if (!isConfigured()) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <h1 className="brand">Econ Sentinel</h1>
          <div className="error-banner" role="alert">
            <span>
              Missing configuration. Copy <code>.env.example</code> to <code>.env</code> and fill in
              the values from the CDK stack outputs (see frontend/README.md).
            </span>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="auth-wrap">
        <Loading label="Checking your session…" />
      </div>
    );
  }

  return isAuthenticated ? <Dashboard /> : <AuthForm />;
}
