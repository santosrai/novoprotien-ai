import React, { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface AuthGuardProps {
  children: React.ReactNode;
  requireRole?: 'admin' | 'moderator';
}

export const AuthGuard: React.FC<AuthGuardProps> = ({ children, requireRole }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const navigate = useNavigate();
  const hasRedirected = useRef(false);

  useEffect(() => {
    if (!isAuthenticated && !hasRedirected.current) {
      hasRedirected.current = true;
      navigate('/signin', { replace: true });
      return;
    }

    if (requireRole && user?.role !== requireRole && user?.role !== 'admin') {
      if (!hasRedirected.current) {
        hasRedirected.current = true;
        navigate('/app', { replace: true });
      }
    }
  }, [isAuthenticated, user, requireRole, navigate]);

  // Reset redirect flag when user becomes authenticated
  useEffect(() => {
    if (isAuthenticated) {
      hasRedirected.current = false;
    }
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    // Show nothing briefly while redirect happens (prevents child components from
    // mounting and firing API calls that would all get 401s)
    return null;
  }

  if (requireRole && user?.role !== requireRole && user?.role !== 'admin') {
    return null;
  }

  return <>{children}</>;
};

