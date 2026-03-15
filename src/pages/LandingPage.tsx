import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import App from '../App';

export const LandingPage: React.FC = () => {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // Authenticated users go to the full app with chat history
  React.useEffect(() => {
    if (isAuthenticated) {
      navigate('/app', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) {
    return null;
  }

  // Unauthenticated users see the same chat UI as the app:
  // - ChatHistorySidebar returns null (auth guard applied in that component)
  // - ProfileMenu in Header shows Sign in / Sign up buttons
  // - ChatPanel shows "What can I do for you?" + suggestion chips
  // - Attempting to send a message redirects to /signin (handled in ChatPanel)
  return <App />;
};
