import React, { useEffect } from 'react';
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

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/signin');
      return;
    }

    if (requireRole && user?.role !== requireRole && user?.role !== 'admin') {
      navigate('/app');
    }
  }, [isAuthenticated, user, requireRole, navigate]);

  if (!isAuthenticated) {
    return null;
  }

  if (requireRole && user?.role !== requireRole && user?.role !== 'admin') {
    return null;
  }

  return <>{children}</>;
};

