import React, { useEffect, useState } from 'react';
import { api } from '../../utils/api';

interface Report {
  id: string;
  report_type: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  created_at: string;
}

export const ReportList: React.FC = () => {
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      const response = await api.get('/reports/my-reports');
      setReports(response.data.reports || []);
    } catch (error) {
      console.error('Failed to load reports:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-4">Loading reports...</div>;
  }

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">My Reports</h2>
      {reports.length === 0 ? (
        <p className="text-gray-500">No reports submitted yet.</p>
      ) : (
        <div className="space-y-4">
          {reports.map((report) => (
            <div key={report.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold">{report.title}</h3>
                <span className={`px-2 py-1 text-xs rounded ${
                  report.status === 'resolved' ? 'bg-green-100 text-green-800' :
                  report.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-gray-100 text-gray-800'
                }`}>
                  {report.status}
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-2">{report.description}</p>
              <div className="flex justify-between text-xs text-gray-500">
                <span>Type: {report.report_type}</span>
                <span>{new Date(report.created_at).toLocaleDateString()}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

