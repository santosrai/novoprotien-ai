import React, { useEffect, useState } from 'react';
import { api } from '../../utils/api';

interface Report {
  id: string;
  user_id: string;
  username: string;
  email: string;
  report_type: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  created_at: string;
  admin_notes?: string;
}

export const ReportReview: React.FC = () => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');

  useEffect(() => {
    loadReports();
  }, [statusFilter]);

  const loadReports = async () => {
    try {
      const params = statusFilter ? { status_filter: statusFilter } : {};
      const response = await api.get('/reports/all', { params });
      setReports(response.data.reports || []);
    } catch (error) {
      console.error('Failed to load reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateReportStatus = async (reportId: string, status: string, notes?: string) => {
    try {
      await api.patch(`/reports/${reportId}`, { status, admin_notes: notes });
      loadReports();
    } catch (error) {
      console.error('Failed to update report:', error);
      alert('Failed to update report status');
    }
  };

  if (loading) {
    return <div>Loading reports...</div>;
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Report Review</h2>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md"
        >
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="reviewing">Reviewing</option>
          <option value="resolved">Resolved</option>
          <option value="dismissed">Dismissed</option>
        </select>
      </div>

      <div className="space-y-4">
        {reports.length === 0 ? (
          <p className="text-gray-500">No reports found.</p>
        ) : (
          reports.map((report) => (
            <div key={report.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <div>
                  <h3 className="font-semibold">{report.title}</h3>
                  <p className="text-sm text-gray-600">By: {report.username} ({report.email})</p>
                </div>
                <div className="flex space-x-2">
                  <span className={`px-2 py-1 text-xs rounded ${
                    report.status === 'resolved' ? 'bg-green-100 text-green-800' :
                    report.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                    report.status === 'reviewing' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {report.status}
                  </span>
                  <span className={`px-2 py-1 text-xs rounded ${
                    report.priority === 'critical' ? 'bg-red-100 text-red-800' :
                    report.priority === 'high' ? 'bg-orange-100 text-orange-800' :
                    report.priority === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {report.priority}
                  </span>
                </div>
              </div>
              
              <p className="text-sm text-gray-700 mb-2">{report.description}</p>
              
              {report.admin_notes && (
                <div className="mb-2 p-2 bg-gray-50 rounded text-sm">
                  <strong>Admin Notes:</strong> {report.admin_notes}
                </div>
              )}
              
              <div className="flex justify-between items-center mt-3">
                <span className="text-xs text-gray-500">
                  {report.report_type} • {new Date(report.created_at).toLocaleDateString()}
                </span>
                <div className="flex space-x-2">
                  <button
                    onClick={() => updateReportStatus(report.id, 'reviewing')}
                    className="px-3 py-1 text-xs bg-blue-100 text-blue-800 rounded hover:bg-blue-200"
                  >
                    Mark Reviewing
                  </button>
                  <button
                    onClick={() => updateReportStatus(report.id, 'resolved')}
                    className="px-3 py-1 text-xs bg-green-100 text-green-800 rounded hover:bg-green-200"
                  >
                    Resolve
                  </button>
                  <button
                    onClick={() => updateReportStatus(report.id, 'dismissed')}
                    className="px-3 py-1 text-xs bg-gray-100 text-gray-800 rounded hover:bg-gray-200"
                  >
                    Dismiss
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

