import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, XCircle, AlertCircle, ExternalLink, Workflow, Download, File, Clock, Info } from 'lucide-react';
import { NodeStatus } from '../components/pipeline-canvas';
import { usePipelineStore } from '../components/pipeline-canvas';

interface PipelineNodeProgress {
  id: string;
  label: string;
  status: NodeStatus;
  result?: any; // result_metadata from node execution
  error?: string;
  duration?: number;
  startedAt?: Date;
  completedAt?: Date;
}

interface PipelineProgressDisplayProps {
  pipelineId: string;
  pipelineName?: string;
  status: 'running' | 'completed' | 'error';
  nodes: PipelineNodeProgress[];
  progress: {
    completed: number;
    total: number;
    percent: number;
  };
  pipelineLink?: string;
  onViewPipeline?: () => void;
}

const getStatusIcon = (status: NodeStatus) => {
  switch (status) {
    case 'running':
      return <Loader2 className="w-4 h-4 animate-spin text-blue-600" />;
    case 'completed':
    case 'success':
      return <CheckCircle2 className="w-4 h-4 text-green-600" />;
    case 'error':
      return <XCircle className="w-4 h-4 text-red-600" />;
    default:
      return <div className="w-4 h-4 rounded-full border-2 border-gray-300" />;
  }
};

export const PipelineProgressDisplay: React.FC<PipelineProgressDisplayProps> = ({
  pipelineId,
  pipelineName,
  status,
  nodes,
  progress,
  pipelineLink,
  onViewPipeline,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null);
  const [showSummary, setShowSummary] = useState(true);
  const { currentExecution } = usePipelineStore();

  const runningNode = nodes.find(n => n.status === 'running');
  const completedNodes = nodes.filter(n => n.status === 'completed' || n.status === 'success');
  const errorNodes = nodes.filter(n => n.status === 'error');

  // Get execution logs for timing information
  const getNodeLog = (nodeId: string) => {
    return currentExecution?.logs.find(log => log.nodeId === nodeId);
  };

  // Format duration
  const formatDuration = (ms?: number) => {
    if (!ms) return 'N/A';
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  // Extract result details from result_metadata
  const getResultDetails = (result: any) => {
    if (!result) return null;
    
    const details: {
      type: string;
      files?: Array<{ filename: string; url: string; type?: string }>;
      sequence?: { length: number; preview?: string };
      metadata?: Record<string, any>;
    } = {
      type: 'unknown',
      metadata: {},
    };

    // Check for output files
    if (result.output_file) {
      details.type = 'file';
      details.files = [{
        filename: result.output_file.filename || 'output.pdb',
        url: result.output_file.file_url || result.output_file.filepath || '',
        type: result.output_file.type || 'pdb_file',
      }];
    }

    // Check for file_info (from input nodes)
    if (result.file_info) {
      details.type = 'input_file';
      details.files = [{
        filename: result.file_info.filename || 'input.pdb',
        url: result.file_info.file_url || '',
        type: 'pdb_file',
      }];
      details.metadata = {
        chains: result.file_info.chains,
        atoms: result.file_info.atoms,
        total_residues: result.file_info.total_residues,
      };
    }

    // Check for sequence
    if (result.sequence) {
      details.type = 'sequence';
      details.sequence = {
        length: typeof result.sequence === 'string' ? result.sequence.length : 0,
        preview: typeof result.sequence === 'string' ? result.sequence.substring(0, 50) : undefined,
      };
    }

    // Check for sequences array (ProteinMPNN)
    if (result.sequences && Array.isArray(result.sequences)) {
      details.type = 'sequences';
      details.sequence = {
        length: result.sequences.length,
      };
      details.metadata = {
        count: result.sequences.length,
        sequences: result.sequences.map((seq: any) => ({
          id: seq.id,
          length: seq.length || (typeof seq.sequence === 'string' ? seq.sequence.length : 0),
        })),
      };
    }

    // Store other metadata
    if (result.filename) details.metadata = { ...details.metadata, filename: result.filename };
    if (result.file_id) details.metadata = { ...details.metadata, file_id: result.file_id };
    if (result.filepath) details.metadata = { ...details.metadata, filepath: result.filepath };

    return details;
  };

  // Generate execution summary
  const getExecutionSummary = () => {
    const summary = {
      totalNodes: nodes.length,
      completed: completedNodes.length,
      failed: errorNodes.length,
      totalDuration: 0,
      outputs: [] as Array<{ type: string; description: string; files?: string[] }>,
    };

    // Calculate total duration and collect outputs
    nodes.forEach(node => {
      const log = getNodeLog(node.id);
      if (log?.duration) {
        summary.totalDuration += log.duration;
      }

      if (node.status === 'completed' || node.status === 'success') {
        const resultDetails = getResultDetails(node.result);
        if (resultDetails) {
          if (resultDetails.files && resultDetails.files.length > 0) {
            summary.outputs.push({
              type: resultDetails.type,
              description: `${node.label}: ${resultDetails.files[0].filename}`,
              files: resultDetails.files.map(f => f.filename),
            });
          } else if (resultDetails.sequence) {
            summary.outputs.push({
              type: resultDetails.type,
              description: `${node.label}: ${resultDetails.type === 'sequences' 
                ? `${resultDetails.sequence.length} sequences generated`
                : `Sequence (${resultDetails.sequence.length} residues)`}`,
            });
          }
        }
      }
    });

    return summary;
  };

  const summary = getExecutionSummary();

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
          <Workflow className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-gray-900">
            {pipelineName || 'Pipeline Execution'}
          </h4>
          <p className="text-xs text-gray-600 mt-1">
            {status === 'running' && runningNode
              ? `Running: ${runningNode.label}`
              : status === 'completed'
              ? 'Pipeline completed successfully'
              : status === 'error'
              ? 'Pipeline execution failed'
              : 'Pipeline execution'}
          </p>
        </div>
        {status === 'running' && (
          <div className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-gray-600">Progress</span>
          <span className="text-gray-900 font-medium">
            {progress.completed} / {progress.total} nodes
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all ${
              status === 'running'
                ? 'bg-blue-600 animate-pulse'
                : status === 'completed'
                ? 'bg-green-600'
                : 'bg-red-600'
            }`}
            style={{ width: `${progress.percent}%` }}
          />
        </div>
      </div>

      {/* Execution Summary */}
      {status === 'completed' && showSummary && (
        <div className="mb-3 p-3 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <Info className="w-4 h-4 text-green-600" />
              <h5 className="text-sm font-medium text-green-800">Execution Summary</h5>
            </div>
            <button
              onClick={() => setShowSummary(false)}
              className="text-xs text-green-600 hover:text-green-800"
            >
              Hide
            </button>
          </div>
          
          {/* Summary Message */}
          <div className="mb-3 p-2 bg-white border border-green-200 rounded">
            <p className="text-sm font-medium text-green-800">
              {summary.failed === 0 
                ? `✓ Pipeline execution completed successfully. All ${summary.completed} node(s) executed.`
                : `⚠ Pipeline execution completed with ${summary.failed} error(s). ${summary.completed} node(s) succeeded.`
              }
            </p>
            {summary.totalDuration > 0 && (
              <p className="text-xs text-gray-600 mt-1 flex items-center space-x-1">
                <Clock className="w-3 h-3" />
                <span>Total execution time: {formatDuration(summary.totalDuration)}</span>
              </p>
            )}
          </div>

          {/* Node Status List with Checkboxes */}
          <div className="space-y-2">
            <div className="text-xs font-medium text-gray-700 mb-1">Node Execution Status:</div>
            {nodes.map((node) => {
              const log = getNodeLog(node.id);
              const resultDetails = getResultDetails(node.result);
              const isSuccess = node.status === 'completed' || node.status === 'success';
              const isError = node.status === 'error';
              
              return (
                <div
                  key={node.id}
                  className={`p-2 rounded border ${
                    isError 
                      ? 'bg-red-50 border-red-200' 
                      : isSuccess 
                      ? 'bg-green-50 border-green-200'
                      : 'bg-gray-50 border-gray-200'
                  }`}
                >
                  <div className="flex items-start space-x-2">
                    {/* Checkbox Status */}
                    <div className="flex-shrink-0 mt-0.5">
                      {isSuccess ? (
                        <div className="w-4 h-4 rounded border-2 border-green-600 bg-green-600 flex items-center justify-center">
                          <CheckCircle2 className="w-3 h-3 text-white" />
                        </div>
                      ) : isError ? (
                        <div className="w-4 h-4 rounded border-2 border-red-600 bg-red-600 flex items-center justify-center">
                          <XCircle className="w-3 h-3 text-white" />
                        </div>
                      ) : (
                        <div className="w-4 h-4 rounded border-2 border-gray-300"></div>
                      )}
                    </div>
                    
                    {/* Node Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className={`text-sm font-medium ${
                          isError ? 'text-red-800' : isSuccess ? 'text-green-800' : 'text-gray-700'
                        }`}>
                          {node.label}
                        </span>
                        {log?.duration && (
                          <span className="text-xs text-gray-500 ml-2">
                            {formatDuration(log.duration)}
                          </span>
                        )}
                      </div>
                      
                      {/* Success Output Details */}
                      {isSuccess && resultDetails && (
                        <div className="mt-1 text-xs space-y-1">
                          {resultDetails.files && resultDetails.files.length > 0 && (
                            <div className="text-green-700">
                              <span className="font-medium">Output:</span>{' '}
                              {resultDetails.files.map((f, idx) => (
                                <span key={idx}>
                                  {f.filename}
                                  {idx < resultDetails.files!.length - 1 && ', '}
                                </span>
                              ))}
                            </div>
                          )}
                          {resultDetails.sequence && (
                            <div className="text-green-700">
                              <span className="font-medium">Output:</span>{' '}
                              {resultDetails.type === 'sequences' 
                                ? `${resultDetails.sequence.length} sequence(s) generated`
                                : `Sequence (${resultDetails.sequence.length} residues)`
                              }
                            </div>
                          )}
                          {resultDetails.metadata && (
                            <div className="text-gray-600">
                              {resultDetails.metadata.chains && (
                                <span>Chains: {Array.isArray(resultDetails.metadata.chains) 
                                  ? resultDetails.metadata.chains.join(', ') 
                                  : resultDetails.metadata.chains
                                }</span>
                              )}
                              {resultDetails.metadata.atoms && (
                                <span className="ml-2">Atoms: {resultDetails.metadata.atoms.toLocaleString()}</span>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* Error Details */}
                      {isError && (
                        <div className="mt-1 text-xs text-red-700">
                          <span className="font-medium">Error:</span>{' '}
                          <span>{node.error || 'Execution failed'}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Outputs Summary */}
          {summary.outputs.length > 0 && (
            <div className="mt-3 pt-3 border-t border-green-200">
              <div className="text-xs font-medium text-green-800 mb-1">Generated Outputs:</div>
              <ul className="space-y-1 text-xs text-green-700">
                {summary.outputs.map((output, idx) => (
                  <li key={idx} className="flex items-start space-x-1">
                    <span className="text-green-600">•</span>
                    <span>{output.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!showSummary && status === 'completed' && (
        <button
          onClick={() => setShowSummary(true)}
          className="mb-3 text-xs text-blue-600 hover:text-blue-800 underline"
        >
          Show execution summary
        </button>
      )}

      {/* Detailed Node Results */}
      {status === 'completed' && completedNodes.length > 0 && (
        <div className="mb-3">
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-full text-left text-xs font-medium text-gray-700 hover:text-gray-900 mb-2"
          >
            {expanded ? 'Hide' : 'Show'} detailed results ({completedNodes.length})
          </button>
          {expanded && (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {nodes.map((node) => {
                const log = getNodeLog(node.id);
                const resultDetails = getResultDetails(node.result);
                const isExpanded = expandedNodeId === node.id;

                return (
                  <div
                    key={node.id}
                    className={`p-3 bg-white border rounded-lg ${
                      node.status === 'error' ? 'border-red-200 bg-red-50' :
                      node.status === 'completed' || node.status === 'success' ? 'border-green-200 bg-green-50' :
                      'border-gray-200'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2 flex-1">
                        {getStatusIcon(node.status)}
                        <div className="flex-1">
                          <div className="text-sm font-medium text-gray-900">{node.label}</div>
                          <div className="text-xs text-gray-500">{node.id}</div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        {log?.duration && (
                          <span className="text-xs text-gray-500 flex items-center space-x-1">
                            <Clock className="w-3 h-3" />
                            <span>{formatDuration(log.duration)}</span>
                          </span>
                        )}
                        {resultDetails && (
                          <button
                            onClick={() => setExpandedNodeId(isExpanded ? null : node.id)}
                            className="text-xs text-blue-600 hover:text-blue-800"
                          >
                            {isExpanded ? 'Hide' : 'Show'} details
                          </button>
                        )}
                      </div>
                    </div>

                    {isExpanded && resultDetails && (
                      <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
                        {/* Output Files */}
                        {resultDetails.files && resultDetails.files.length > 0 && (
                          <div>
                            <div className="text-xs font-medium text-gray-700 mb-1">Output Files:</div>
                            <div className="space-y-1">
                              {resultDetails.files.map((file, idx) => (
                                <div key={idx} className="flex items-center justify-between p-2 bg-white border border-gray-200 rounded">
                                  <div className="flex items-center space-x-2 flex-1 min-w-0">
                                    <File className="w-3 h-3 text-gray-600 flex-shrink-0" />
                                    <span className="text-xs text-gray-700 truncate">{file.filename}</span>
                                  </div>
                                  {file.url && (
                                    <a
                                      href={file.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="ml-2 px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 flex items-center space-x-1"
                                    >
                                      <Download className="w-3 h-3" />
                                      <span>Download</span>
                                    </a>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Sequence Output */}
                        {resultDetails.sequence && (
                          <div>
                            <div className="text-xs font-medium text-gray-700 mb-1">
                              {resultDetails.type === 'sequences' ? 'Sequences Generated:' : 'Sequence:'}
                            </div>
                            <div className="p-2 bg-white border border-gray-200 rounded">
                              {resultDetails.type === 'sequences' ? (
                                <div className="text-xs text-gray-700">
                                  {resultDetails.sequence.length} sequence(s) generated
                                  {resultDetails.metadata?.sequences && (
                                    <div className="mt-1 space-y-1">
                                      {resultDetails.metadata.sequences.slice(0, 3).map((seq: any, idx: number) => (
                                        <div key={idx} className="text-xs text-gray-600">
                                          • Sequence {seq.id || idx + 1}: {seq.length} residues
                                        </div>
                                      ))}
                                      {resultDetails.metadata.sequences.length > 3 && (
                                        <div className="text-xs text-gray-500">
                                          ... and {resultDetails.metadata.sequences.length - 3} more
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ) : (
                                <div className="text-xs text-gray-700">
                                  Length: {resultDetails.sequence.length} residues
                                  {resultDetails.sequence.preview && (
                                    <div className="mt-1 font-mono text-xs bg-gray-50 p-2 rounded break-all">
                                      {resultDetails.sequence.preview}...
                                    </div>
                                  )}
                                </div>
                              )}
                            </div>
                          </div>
                        )}

                        {/* Metadata */}
                        {resultDetails.metadata && Object.keys(resultDetails.metadata).length > 0 && (
                          <div>
                            <div className="text-xs font-medium text-gray-700 mb-1">Metadata:</div>
                            <div className="p-2 bg-white border border-gray-200 rounded">
                              <div className="space-y-1 text-xs text-gray-600">
                                {resultDetails.metadata.chains && (
                                  <div>Chains: {Array.isArray(resultDetails.metadata.chains) ? resultDetails.metadata.chains.join(', ') : resultDetails.metadata.chains}</div>
                                )}
                                {resultDetails.metadata.atoms && (
                                  <div>Atoms: {resultDetails.metadata.atoms.toLocaleString()}</div>
                                )}
                                {resultDetails.metadata.total_residues && (
                                  <div>Residues: {resultDetails.metadata.total_residues}</div>
                                )}
                                {resultDetails.metadata.file_id && (
                                  <div>File ID: {resultDetails.metadata.file_id}</div>
                                )}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {node.error && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                        <strong>Error:</strong> {node.error}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Errors */}
      {errorNodes.length > 0 && (
        <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded">
          <div className="text-xs font-medium text-red-800 mb-1">Errors:</div>
          <div className="space-y-1">
            {errorNodes.map((node) => (
              <div key={node.id} className="text-xs text-red-700">
                {node.label}: {node.error || 'Execution failed'}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center space-x-2">
        {(pipelineLink || onViewPipeline) && (
          <>
            <button
              onClick={onViewPipeline}
              className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
            >
              <Workflow className="w-3 h-3" />
              <span>View in Pipeline Editor</span>
            </button>
            {pipelineLink && (
              <a
                href={pipelineLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center space-x-1 px-3 py-1.5 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
              >
                <ExternalLink className="w-3 h-3" />
                <span>Open in New Tab</span>
              </a>
            )}
          </>
        )}
      </div>
    </div>
  );
};

