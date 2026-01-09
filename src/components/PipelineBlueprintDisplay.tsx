import React, { useState } from 'react';
import { Check, X, Workflow, FileInput, Sparkles, Dna, Layers } from 'lucide-react';
import { PipelineBlueprint } from '../components/pipeline-canvas';
import { usePipelineStore } from '../components/pipeline-canvas';
import { useAppStore } from '../stores/appStore';

interface PipelineBlueprintDisplayProps {
  blueprint: PipelineBlueprint;
  rationale?: string;
  onApprove?: (selectedNodeIds: string[]) => void;
  onReject?: () => void;
  isApproved?: boolean;
}

const nodeIcons: Record<string, React.ReactNode> = {
  input_node: <FileInput className="w-4 h-4" />,
  rfdiffusion_node: <Sparkles className="w-4 h-4" />,
  proteinmpnn_node: <Dna className="w-4 h-4" />,
  alphafold_node: <Layers className="w-4 h-4" />,
};

const nodeColors: Record<string, string> = {
  input_node: 'bg-blue-500',
  rfdiffusion_node: 'bg-purple-500',
  proteinmpnn_node: 'bg-green-500',
  alphafold_node: 'bg-orange-500',
};

export const PipelineBlueprintDisplay: React.FC<PipelineBlueprintDisplayProps> = ({
  blueprint,
  rationale,
  onApprove,
  onReject,
  isApproved = false,
}) => {
  const { rejectBlueprint, approveBlueprintWithSelection } = usePipelineStore();
  const { setActivePane } = useAppStore();
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [localApproved, setLocalApproved] = useState(isApproved);

  // Initialize with all nodes selected by default
  React.useEffect(() => {
    if (selectedNodes.size === 0 && blueprint.nodes.length > 0) {
      setSelectedNodes(new Set(blueprint.nodes.map(n => n.id)));
    }
  }, [blueprint.nodes]);

  // Update local approved state when prop changes
  React.useEffect(() => {
    setLocalApproved(isApproved);
  }, [isApproved]);

  const handleNodeToggle = (nodeId: string) => {
    const newSelected = new Set(selectedNodes);
    if (newSelected.has(nodeId)) {
      newSelected.delete(nodeId);
    } else {
      newSelected.add(nodeId);
    }
    setSelectedNodes(newSelected);
  };

  const handleApprove = () => {
    if (selectedNodes.size === 0) {
      return; // Don't allow approval with no nodes selected
    }
    
    // Approve blueprint with selected nodes (empty configs for now, user will configure later)
    const pipeline = approveBlueprintWithSelection(Array.from(selectedNodes), {});
    
    if (pipeline) {
      console.log('[PipelineBlueprintDisplay] Blueprint approved, pipeline created:', pipeline.id);
      console.log('[PipelineBlueprintDisplay] Navigating to pipeline canvas for configuration');
      
      // Mark as approved locally
      setLocalApproved(true);
      
      // Dispatch event to signal blueprint approval (for auto-selection)
      window.dispatchEvent(new CustomEvent('blueprint-approved'));
      
      // Navigate to pipeline canvas so user can configure node parameters
      setActivePane('pipeline');
      
      // Call optional callback (this will update the chat message)
      if (onApprove) {
        onApprove(Array.from(selectedNodes));
      }
    } else {
      console.warn('[PipelineBlueprintDisplay] Failed to approve blueprint');
    }
  };

  const handleReject = () => {
    rejectBlueprint();
    if (onReject) {
      onReject();
    }
  };

  return (
    <div className="mt-3 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg">
      <div className="flex items-center space-x-2 mb-3">
        <div className="w-8 h-8 bg-indigo-600 rounded-full flex items-center justify-center">
          <Workflow className="w-5 h-5 text-white" />
        </div>
        <div className="flex-1">
          <h4 className="font-medium text-gray-900">Pipeline Blueprint</h4>
          {rationale && (
            <p className="text-xs text-gray-600 mt-1">{rationale}</p>
          )}
          {blueprint.rationale && (
            <p className="text-xs text-gray-600 mt-1">{blueprint.rationale}</p>
          )}
        </div>
      </div>

      {blueprint.missing_resources && blueprint.missing_resources.length > 0 && (
        <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
          <strong>Missing resources:</strong> {blueprint.missing_resources.join(', ')}
        </div>
      )}

      <div className="mb-3">
        <div className="text-xs font-medium text-gray-700 mb-2">
          Select nodes to include ({selectedNodes.size} of {blueprint.nodes.length} selected):
        </div>
        <div className="space-y-2">
          {blueprint.nodes
            .sort((a, b) => {
              // Sort input nodes first, then others maintain their order
              if (a.type === 'input_node' && b.type !== 'input_node') return -1;
              if (a.type !== 'input_node' && b.type === 'input_node') return 1;
              return 0;
            })
            .map((node) => {
            const isSelected = selectedNodes.has(node.id);
            return (
              <div
                key={node.id}
                className={`flex items-center space-x-2 p-2 bg-white border rounded cursor-pointer transition-colors ${
                  isSelected 
                    ? 'border-indigo-500 bg-indigo-50' 
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => !isApproved && handleNodeToggle(node.id)}
              >
                <div className="flex items-center justify-center w-5 h-5 border-2 rounded border-gray-300 flex-shrink-0">
                  {isSelected && (
                    <Check className="w-4 h-4 text-indigo-600" />
                  )}
                </div>
                <div className={`${nodeColors[node.type] || 'bg-gray-500'} text-white p-1.5 rounded flex-shrink-0`}>
                  {nodeIcons[node.type] || <Workflow className="w-3 h-3" />}
                </div>
                <div className="flex-1">
                  <div className="text-sm font-medium text-gray-900">{node.label}</div>
                  <div className="text-xs text-gray-500">{node.type}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {blueprint.edges.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-medium text-gray-700 mb-2">
            Connections ({blueprint.edges.length}):
          </div>
          <div className="space-y-1">
            {blueprint.edges.map((edge, index) => {
              const sourceNode = blueprint.nodes.find(n => n.id === edge.source);
              const targetNode = blueprint.nodes.find(n => n.id === edge.target);
              return (
                <div key={index} className="text-xs text-gray-600">
                  {sourceNode?.label || edge.source} → {targetNode?.label || edge.target}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {!localApproved && (
        <div className="flex items-center space-x-2 mt-4">
          <button
            onClick={handleApprove}
            disabled={selectedNodes.size === 0}
            className={`flex-1 inline-flex items-center justify-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
              selectedNodes.size === 0
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
            }`}
          >
            <Check className="w-4 h-4" />
            <span>Approve & Configure Parameters</span>
          </button>
          <button
            onClick={handleReject}
            className="inline-flex items-center justify-center space-x-2 px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
          >
            <X className="w-4 h-4" />
            <span>Reject</span>
          </button>
        </div>
      )}
      {localApproved && (
        <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center space-x-2 mb-1">
            <Check className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-800">Pipeline Approved</span>
          </div>
          <p className="text-xs text-green-700 mt-1">
            Pipeline created successfully with {selectedNodes.size} node{selectedNodes.size === 1 ? '' : 's'}. 
            You can now configure parameters for each node in the pipeline canvas.
          </p>
        </div>
      )}
    </div>
  );
};

