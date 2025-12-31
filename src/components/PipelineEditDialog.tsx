import React from 'react';
import { Pipeline, PipelineNode } from './pipeline-canvas/types';
import { X, FileText, Sparkles, Dna, Atom, Upload } from 'lucide-react';

interface PipelineEditDialogProps {
  isOpen: boolean;
  onClose: () => void;
  pipeline: Pipeline;
  onNodeSelected: (nodeId: string, nodeType: string) => void;
}

const nodeTypeIcons: Record<string, React.ReactNode> = {
  input_node: <Upload className="w-5 h-5" />,
  rfdiffusion_node: <Sparkles className="w-5 h-5" />,
  proteinmpnn_node: <Dna className="w-5 h-5" />,
  alphafold_node: <Atom className="w-5 h-5" />,
};

const nodeTypeLabels: Record<string, string> = {
  input_node: 'Input',
  rfdiffusion_node: 'RFdiffusion',
  proteinmpnn_node: 'ProteinMPNN',
  alphafold_node: 'AlphaFold',
};

const nodeTypeColors: Record<string, string> = {
  input_node: 'bg-blue-500/20 border-blue-500/50 text-blue-400',
  rfdiffusion_node: 'bg-purple-500/20 border-purple-500/50 text-purple-400',
  proteinmpnn_node: 'bg-green-500/20 border-green-500/50 text-green-400',
  alphafold_node: 'bg-orange-500/20 border-orange-500/50 text-orange-400',
};

export const PipelineEditDialog: React.FC<PipelineEditDialogProps> = ({
  isOpen,
  onClose,
  pipeline,
  onNodeSelected,
}) => {
  if (!isOpen) return null;

  const handleNodeClick = (node: PipelineNode) => {
    onNodeSelected(node.id, node.type);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={onClose}>
      <div
        className="bg-[#1e1e32] rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700/50">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center">
              <FileText className="w-4 h-4 text-white" />
            </div>
            <h2 className="text-lg font-semibold text-white">Edit Pipeline</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-4">
            <h3 className="text-sm font-medium text-gray-300 mb-1">{pipeline.name}</h3>
            <p className="text-xs text-gray-500">
              Select a node to edit its parameters. Other nodes will remain unchanged.
            </p>
          </div>

          {pipeline.nodes.length === 0 ? (
            <div className="text-center py-8">
              <p className="text-sm text-gray-500">No nodes in this pipeline</p>
            </div>
          ) : (
            <div className="space-y-2">
              {pipeline.nodes.map((node) => {
                const nodeType = node.type;
                const icon = nodeTypeIcons[nodeType] || <FileText className="w-5 h-5" />;
                const label = nodeTypeLabels[nodeType] || nodeType;
                const colorClass = nodeTypeColors[nodeType] || 'bg-gray-500/20 border-gray-500/50 text-gray-400';

                return (
                  <div
                    key={node.id}
                    onClick={() => handleNodeClick(node)}
                    className={`flex items-center gap-3 p-4 rounded-lg border ${colorClass} hover:opacity-80 cursor-pointer transition-all group`}
                  >
                    <div className={`w-10 h-10 flex items-center justify-center rounded ${colorClass.replace('border', 'bg').replace('/50', '/30')}`}>
                      {icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h4 className="text-sm font-medium text-white truncate">
                        {node.label || label}
                      </h4>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {label} • Click to edit parameters
                      </p>
                      {node.config && Object.keys(node.config).length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {Object.entries(node.config).slice(0, 3).map(([key, value]) => {
                            if (value === null || value === undefined || value === '') return null;
                            return (
                              <span
                                key={key}
                                className="text-xs px-2 py-0.5 bg-gray-700/50 rounded text-gray-300"
                              >
                                {key}: {String(value).length > 20 ? String(value).substring(0, 20) + '...' : String(value)}
                              </span>
                            );
                          })}
                        </div>
                      )}
                    </div>
                    <div className="text-gray-400 group-hover:text-white transition-colors">
                      <X className="w-4 h-4 rotate-45" />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

