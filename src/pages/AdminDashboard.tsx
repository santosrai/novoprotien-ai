import React, { useState } from 'react';
import { UserManagement } from '../components/admin/UserManagement';
import { CreditManagement } from '../components/admin/CreditManagement';
import { ReportReview } from '../components/admin/ReportReview';
import { AdminStats } from '../components/admin/AdminStats';

export const AdminDashboard: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'stats' | 'users' | 'credits' | 'reports'>('stats');

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">Admin Dashboard</h1>
            <a
              href="/app"
              className="text-sm text-indigo-600 hover:text-indigo-800"
            >
              Back to App
            </a>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="bg-white rounded-lg shadow">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              {[
                { id: 'stats', label: 'Statistics' },
                { id: 'users', label: 'Users' },
                { id: 'credits', label: 'Credits' },
                { id: 'reports', label: 'Reports' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`px-6 py-3 text-sm font-medium border-b-2 ${
                    activeTab === tab.id
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'stats' && <AdminStats />}
            {activeTab === 'users' && <UserManagement />}
            {activeTab === 'credits' && <CreditManagement />}
            {activeTab === 'reports' && <ReportReview />}
          </div>
        </div>
      </div>
    </div>
  );
};

