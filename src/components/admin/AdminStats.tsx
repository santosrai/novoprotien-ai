import React, { useEffect, useState } from 'react';
import { api } from '../../utils/api';

interface Stats {
  total_users: number;
  active_users: number;
  total_credits: number;
  pending_reports: number;
  recent_signups: number;
}

export const AdminStats: React.FC = () => {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const response = await api.get('/admin/stats');
      setStats(response.data.stats);
    } catch (error) {
      console.error('Failed to load stats:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading statistics...</div>;
  }

  if (!stats) {
    return <div>Failed to load statistics</div>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
      <div className="bg-blue-50 p-4 rounded-lg">
        <div className="text-sm text-blue-600 font-medium">Total Users</div>
        <div className="text-2xl font-bold text-blue-900">{stats.total_users}</div>
      </div>
      <div className="bg-green-50 p-4 rounded-lg">
        <div className="text-sm text-green-600 font-medium">Active Users</div>
        <div className="text-2xl font-bold text-green-900">{stats.active_users}</div>
      </div>
      <div className="bg-purple-50 p-4 rounded-lg">
        <div className="text-sm text-purple-600 font-medium">Total Credits</div>
        <div className="text-2xl font-bold text-purple-900">{stats.total_credits}</div>
      </div>
      <div className="bg-yellow-50 p-4 rounded-lg">
        <div className="text-sm text-yellow-600 font-medium">Pending Reports</div>
        <div className="text-2xl font-bold text-yellow-900">{stats.pending_reports}</div>
      </div>
      <div className="bg-indigo-50 p-4 rounded-lg">
        <div className="text-sm text-indigo-600 font-medium">Recent Signups (7d)</div>
        <div className="text-2xl font-bold text-indigo-900">{stats.recent_signups}</div>
      </div>
    </div>
  );
};

