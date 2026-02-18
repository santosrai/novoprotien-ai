import { useState, useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
  CartesianGrid,
} from 'recharts';
import {
  Shield,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Zap,
} from 'lucide-react';
import type { ValidationReport, ValidationSuggestion } from '../types/validation';

interface ValidationPanelProps {
  report: ValidationReport;
  onColorByConfidence?: () => void;
  onFocusResidues?: (residues: { chain_id: string; residue_number: number }[]) => void;
}

const GRADE_COLORS: Record<string, string> = {
  A: 'bg-green-500',
  B: 'bg-blue-500',
  C: 'bg-yellow-500',
  D: 'bg-orange-500',
  F: 'bg-red-500',
};

const GRADE_TEXT_COLORS: Record<string, string> = {
  A: 'text-green-500',
  B: 'text-blue-500',
  C: 'text-yellow-500',
  D: 'text-orange-500',
  F: 'text-red-500',
};

function getScoreColor(score: number): string {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-blue-500';
  if (score >= 40) return 'bg-yellow-500';
  if (score >= 20) return 'bg-orange-500';
  return 'bg-red-500';
}

function getPlddtColor(value: number): string {
  if (value >= 90) return '#0053d6';
  if (value >= 70) return '#65cbf3';
  if (value >= 50) return '#ffdb13';
  return '#ff7d45';
}

function getRamaColor(region: string): string {
  if (region === 'favored') return '#22c55e';
  if (region === 'allowed') return '#eab308';
  return '#ef4444';
}

function getSuggestionIcon(type: ValidationSuggestion['type']) {
  switch (type) {
    case 'success':
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    case 'error':
      return <XCircle className="w-5 h-5 text-red-500" />;
    case 'clashes':
      return <Zap className="w-5 h-5 text-orange-500" />;
    case 'confidence':
      return <Info className="w-5 h-5 text-blue-500" />;
    case 'geometry':
      return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
    default:
      return <Info className="w-5 h-5 text-gray-500" />;
  }
}

function getSeverityBorderColor(severity: ValidationSuggestion['severity']): string {
  switch (severity) {
    case 'critical':
      return 'border-l-red-500';
    case 'high':
      return 'border-l-orange-500';
    case 'medium':
      return 'border-l-yellow-500';
    case 'low':
      return 'border-l-green-500';
    default:
      return 'border-l-gray-500';
  }
}

type SectionName = 'plddt' | 'ramachandran' | 'clashes';

export default function ValidationPanel({
  report,
  onColorByConfidence,
  onFocusResidues,
}: ValidationPanelProps) {
  const [expandedSection, setExpandedSection] = useState<SectionName | null>(null);

  const toggleSection = (section: SectionName) => {
    setExpandedSection((prev) => (prev === section ? null : section));
  };

  // Downsample pLDDT data to at most 200 bars
  const plddtChartData = useMemo(() => {
    const raw = report.plddt_per_residue;
    if (raw.length <= 200) {
      return raw.map((r, i) => ({
        index: i,
        plddt: r.plddt,
        label: `${r.chain_id}:${r.residue_name}${r.residue_number}`,
        color: getPlddtColor(r.plddt),
      }));
    }
    const step = Math.ceil(raw.length / 200);
    const downsampled: { index: number; plddt: number; label: string; color: string }[] = [];
    for (let i = 0; i < raw.length; i += step) {
      const chunk = raw.slice(i, i + step);
      const avg = chunk.reduce((sum, c) => sum + c.plddt, 0) / chunk.length;
      downsampled.push({
        index: Math.floor(i / step),
        plddt: Math.round(avg * 10) / 10,
        label: `${chunk[0].chain_id}:${chunk[0].residue_number}-${chunk[chunk.length - 1].residue_number}`,
        color: getPlddtColor(avg),
      });
    }
    return downsampled;
  }, [report.plddt_per_residue]);

  const ramaChartData = useMemo(() => {
    return report.rama_data.map((pt) => ({
      phi: pt.phi,
      psi: pt.psi,
      region: pt.region,
      label: `${pt.chain_id}:${pt.residue_name}${pt.residue_number}`,
      color: getRamaColor(pt.region),
    }));
  }, [report.rama_data]);

  const clashesLimited = report.clash_details.slice(0, 20);

  return (
    <div className="flex flex-col gap-4 p-4 bg-gray-900 rounded-lg border border-gray-700 text-white">
      {/* Header: Grade + Score */}
      <div className="flex items-center gap-4">
        <div
          className={`flex items-center justify-center w-16 h-16 rounded-xl text-3xl font-bold text-white ${GRADE_COLORS[report.grade] ?? 'bg-gray-500'}`}
        >
          {report.grade}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Shield className="w-5 h-5 text-gray-400" />
            <span className="text-lg font-semibold">Validation Report</span>
            <span className={`text-sm font-medium ${GRADE_TEXT_COLORS[report.grade] ?? 'text-gray-400'}`}>
              Grade {report.grade}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-3 bg-gray-700 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${getScoreColor(report.overall_score)}`}
                style={{ width: `${report.overall_score}%` }}
              />
            </div>
            <span className="text-sm font-mono text-gray-300 w-12 text-right">
              {report.overall_score}
            </span>
          </div>
          <div className="flex gap-4 mt-1 text-xs text-gray-400">
            <span>{report.total_residues} residues</span>
            <span>{report.chains.length} chain{report.chains.length !== 1 ? 's' : ''}</span>
            <span>Source: {report.source}</span>
          </div>
        </div>
      </div>

      {/* Suggestion Cards */}
      {report.suggestions.length > 0 && (
        <div className="flex flex-col gap-2">
          {report.suggestions.map((s, i) => (
            <div
              key={i}
              className={`flex items-start gap-3 p-3 bg-gray-800 rounded-lg border-l-4 ${getSeverityBorderColor(s.severity)}`}
            >
              <div className="mt-0.5">{getSuggestionIcon(s.type)}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-100">{s.message}</p>
                <p className="text-xs text-gray-400 mt-0.5">{s.detail}</p>
                {s.action && (
                  <button
                    className="text-xs text-blue-400 hover:text-blue-300 mt-1 underline"
                    onClick={() => {
                      if (
                        onFocusResidues &&
                        s.residues.length > 0 &&
                        s.residues[0].chain_id &&
                        s.residues[0].residue_number
                      ) {
                        onFocusResidues(
                          s.residues as { chain_id: string; residue_number: number }[]
                        );
                      }
                    }}
                  >
                    {s.action}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* pLDDT Section */}
      <div className="border border-gray-700 rounded-lg overflow-hidden">
        <button
          className="flex items-center justify-between w-full px-4 py-3 bg-gray-800 hover:bg-gray-750 transition-colors"
          onClick={() => toggleSection('plddt')}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">pLDDT Confidence</span>
            <span className="text-xs text-gray-400">
              Mean: {report.plddt_mean.toFixed(1)} | High conf: {report.total_residues > 0 ? ((report.plddt_high_confidence / report.total_residues) * 100).toFixed(1) : '0.0'}%
            </span>
          </div>
          {expandedSection === 'plddt' ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </button>
        {expandedSection === 'plddt' && (
          <div className="p-4">
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={plddtChartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                  <XAxis dataKey="index" hide />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#9ca3af' }} width={30} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#e5e7eb',
                      fontSize: '12px',
                    }}
                    formatter={(value: unknown) => [`${value}`, 'pLDDT']}
                    labelFormatter={(_label: unknown, payload: unknown) => {
                      const items = payload as Array<{ payload?: { label?: string } }> | undefined;
                      if (items && items.length > 0 && items[0].payload) {
                        return items[0].payload.label ?? '';
                      }
                      return '';
                    }}
                  />
                  <Bar dataKey="plddt" radius={[1, 1, 0, 0]}>
                    {plddtChartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            {/* Legend */}
            <div className="flex flex-wrap gap-3 mt-2 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#0053d6' }} /> Very high (90+)
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#65cbf3' }} /> Confident (70-90)
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#ffdb13' }} /> Low (50-70)
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#ff7d45' }} /> Very low (&lt;50)
              </span>
            </div>
            {onColorByConfidence && (
              <button
                className="mt-3 px-3 py-1.5 text-xs font-medium bg-blue-600 hover:bg-blue-500 rounded-md transition-colors"
                onClick={onColorByConfidence}
              >
                Color structure by confidence
              </button>
            )}
          </div>
        )}
      </div>

      {/* Ramachandran Section */}
      <div className="border border-gray-700 rounded-lg overflow-hidden">
        <button
          className="flex items-center justify-between w-full px-4 py-3 bg-gray-800 hover:bg-gray-750 transition-colors"
          onClick={() => toggleSection('ramachandran')}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Ramachandran Plot</span>
            <span className="text-xs text-gray-400">
              Favored: {report.rama_favored_pct.toFixed(1)}% | Outliers: {report.rama_outlier_pct.toFixed(1)}%
            </span>
          </div>
          {expandedSection === 'ramachandran' ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </button>
        {expandedSection === 'ramachandran' && (
          <div className="p-4">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 10, right: 10, bottom: 20, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis
                    type="number"
                    dataKey="phi"
                    domain={[-180, 180]}
                    name="Phi"
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    label={{ value: 'Phi (\u03C6)', position: 'bottom', offset: 5, fontSize: 11, fill: '#9ca3af' }}
                  />
                  <YAxis
                    type="number"
                    dataKey="psi"
                    domain={[-180, 180]}
                    name="Psi"
                    tick={{ fontSize: 10, fill: '#9ca3af' }}
                    label={{ value: 'Psi (\u03C8)', angle: -90, position: 'insideLeft', offset: 0, fontSize: 11, fill: '#9ca3af' }}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1f2937',
                      border: '1px solid #374151',
                      borderRadius: '8px',
                      color: '#e5e7eb',
                      fontSize: '12px',
                    }}
                    content={({ payload }) => {
                      if (!payload || payload.length === 0) return null;
                      const d = payload[0].payload as {
                        label: string;
                        phi: number;
                        psi: number;
                        region: string;
                      };
                      return (
                        <div className="bg-gray-800 border border-gray-600 rounded-lg p-2 text-xs">
                          <p className="font-medium text-gray-100">{d.label}</p>
                          <p className="text-gray-400">
                            Phi: {d.phi.toFixed(1)} | Psi: {d.psi.toFixed(1)}
                          </p>
                          <p className="text-gray-400 capitalize">Region: {d.region}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter data={ramaChartData} shape="circle">
                    {ramaChartData.map((entry, idx) => (
                      <Cell key={idx} fill={entry.color} r={3} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            {/* Legend */}
            <div className="flex gap-4 mt-2 text-xs text-gray-400">
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full bg-green-500" /> Favored ({report.rama_favored})
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full bg-yellow-500" /> Allowed ({report.rama_allowed})
              </span>
              <span className="flex items-center gap-1">
                <span className="w-3 h-3 rounded-full bg-red-500" /> Outlier ({report.rama_outlier})
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Clashes Section */}
      <div className="border border-gray-700 rounded-lg overflow-hidden">
        <button
          className="flex items-center justify-between w-full px-4 py-3 bg-gray-800 hover:bg-gray-750 transition-colors"
          onClick={() => toggleSection('clashes')}
        >
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Steric Clashes</span>
            <span
              className={`text-xs px-1.5 py-0.5 rounded-full ${
                report.clash_count === 0
                  ? 'bg-green-900/50 text-green-400'
                  : report.clash_count <= 5
                    ? 'bg-yellow-900/50 text-yellow-400'
                    : 'bg-red-900/50 text-red-400'
              }`}
            >
              {report.clash_count} clash{report.clash_count !== 1 ? 'es' : ''}
            </span>
          </div>
          {expandedSection === 'clashes' ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </button>
        {expandedSection === 'clashes' && (
          <div className="p-4">
            {clashesLimited.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-2">No steric clashes detected.</p>
            ) : (
              <div className="flex flex-col gap-1">
                {clashesLimited.map((clash, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between px-3 py-2 bg-gray-800 rounded text-xs"
                  >
                    <div className="flex items-center gap-2">
                      <Zap className="w-3.5 h-3.5 text-orange-400" />
                      <span className="font-mono text-gray-200">{clash.atom1}</span>
                      <span className="text-gray-500">&mdash;</span>
                      <span className="font-mono text-gray-200">{clash.atom2}</span>
                    </div>
                    <span className="text-gray-400">
                      {clash.distance.toFixed(2)} &Aring;
                    </span>
                  </div>
                ))}
                {report.clash_details.length > 20 && (
                  <p className="text-xs text-gray-500 text-center mt-1">
                    Showing 20 of {report.clash_details.length} clashes
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
