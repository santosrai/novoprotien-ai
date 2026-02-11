import React, { useState } from 'react';
import { Check, X, Workflow, FileInput, Sparkles, Dna, Layers, Settings, ExternalLink } from 'lucide-react';
import { PipelineBlueprint, PipelineNodeBlueprint } from '../components/pipeline-canvas';
import { usePipelineStore } from '../components/pipeline-canvas';
import { useAppStore } from '../stores/appStore';
import { useChatHistoryStore } from '../stores/chatHistoryStore';
import { NodeConfigModal } from './pipeline-canvas/components/NodeConfigModal';
import { ErrorDetails, ErrorCategory, ErrorSeverity } from '../utils/errorHandler';
import { v4 as uuidv4 } from 'uuid';

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
  const { setActivePane, setViewerVisible } = useAppStore();
  const { activeSessionId, addMessageToSession } = useChatHistoryStore();
  const [selectedNodes, setSelectedNodes] = useState<Set<string>>(new Set());
  const [localApproved, setLocalApproved] = useState(isApproved);
  const [isRejected, setIsRejected] = useState(false);
  const [configuringNodeId, setConfiguringNodeId] = useState<string | null>(null);
  const [localBlueprint, setLocalBlueprint] = useState<PipelineBlueprint>(blueprint);
  const hasUserInteracted = React.useRef(false);

  // Initialize with all nodes selected by default
  React.useEffect(() => {
    if (selectedNodes.size === 0 && localBlueprint.nodes.length > 0) {
      setSelectedNodes(new Set(localBlueprint.nodes.map(n => n.id)));
    }
  }, [localBlueprint.nodes]);

  // Update local approved state when prop changes (only if user hasn't interacted yet, or if prop becomes true)
  React.useEffect(() => {
    // Only sync from props if:
    // 1. User hasn't interacted yet, OR
    // 2. The prop is true (meaning it was approved externally, e.g., from database)
    if (!hasUserInteracted.current || isApproved) {
      setLocalApproved(isApproved);
    }
  }, [isApproved]);

  // Update local blueprint when prop changes
  React.useEffect(() => {
    setLocalBlueprint(blueprint);
  }, [blueprint]);

  const handleNodeToggle = (nodeId: string) => {
    const newSelected = new Set(selectedNodes);
    if (newSelected.has(nodeId)) {
      newSelected.delete(nodeId);
    } else {
      newSelected.add(nodeId);
    }
    setSelectedNodes(newSelected);
  };

  const generatePipelineSummary = (selectedNodeIds: string[]): string => {
    const selectedNodesList = localBlueprint.nodes.filter(n => selectedNodeIds.includes(n.id));
    const nodeTypeCounts: Record<string, number> = {};
    
    selectedNodesList.forEach(node => {
      nodeTypeCounts[node.type] = (nodeTypeCounts[node.type] || 0) + 1;
    });
    
    const nodeDescriptions: string[] = [];
    if (nodeTypeCounts['input_node']) {
      nodeDescriptions.push(`${nodeTypeCounts['input_node']} input node${nodeTypeCounts['input_node'] > 1 ? 's' : ''} (PDB file input)`);
    }
    if (nodeTypeCounts['rfdiffusion_node']) {
      nodeDescriptions.push(`${nodeTypeCounts['rfdiffusion_node']} RFdiffusion node${nodeTypeCounts['rfdiffusion_node'] > 1 ? 's' : ''} (de novo backbone design)`);
    }
    if (nodeTypeCounts['proteinmpnn_node']) {
      nodeDescriptions.push(`${nodeTypeCounts['proteinmpnn_node']} ProteinMPNN node${nodeTypeCounts['proteinmpnn_node'] > 1 ? 's' : ''} (sequence design)`);
    }
    if (nodeTypeCounts['alphafold_node']) {
      nodeDescriptions.push(`${nodeTypeCounts['alphafold_node']} AlphaFold node${nodeTypeCounts['alphafold_node'] > 1 ? 's' : ''} (structure prediction)`);
    }
    
    const summary = `I've created a pipeline with ${selectedNodesList.length} node${selectedNodesList.length > 1 ? 's' : ''}: ${nodeDescriptions.join(', ')}.`;
    
    const workflowDescription: string[] = [];
    const edges = localBlueprint.edges.filter(e => 
      selectedNodeIds.includes(e.source) && selectedNodeIds.includes(e.target)
    );
    
    if (edges.length > 0) {
      workflowDescription.push(`The workflow connects ${edges.length} node${edges.length > 1 ? 's' : ''} in sequence.`);
    }
    
    let fullSummary = summary;
    if (workflowDescription.length > 0) {
      fullSummary += ' ' + workflowDescription.join(' ');
    }
    
    fullSummary += ` The pipeline is now ready for execution. Please review the configuration in the pipeline canvas and run it to see the results.`;
    
    return fullSummary;
  };

  const handleApprove = async () => {
    if (selectedNodes.size === 0) {
      return; // Don't allow approval with no nodes selected
    }
    
    // Mark as approved immediately to hide buttons
    hasUserInteracted.current = true;
    setLocalApproved(true);
    
    try {
      // Build node configs map from localBlueprint (includes any configurations made via modal)
      const nodeConfigs: Record<string, Record<string, any>> = {};
      localBlueprint.nodes.forEach(node => {
        if (selectedNodes.has(node.id) && node.config) {
          nodeConfigs[node.id] = node.config;
        }
      });
      
      // Approve blueprint with selected nodes and their configs
      const pipeline = approveBlueprintWithSelection(Array.from(selectedNodes), nodeConfigs);
      
      if (!pipeline) {
        throw new Error('Failed to create pipeline from blueprint. Please try again or contact support if the issue persists.');
      }
      
      console.log('[PipelineBlueprintDisplay] Blueprint approved, pipeline created:', pipeline.id);
      console.log('[PipelineBlueprintDisplay] Navigating to pipeline canvas for configuration');
      
      // Dispatch event to signal blueprint approval (for auto-selection)
      window.dispatchEvent(new CustomEvent('blueprint-approved'));
      
      // Navigate to pipeline canvas so user can configure node parameters
      setActivePane('pipeline');
      setViewerVisible(true); // Ensure the layout shows the pipeline canvas
      
      // Generate AI summary message and add to chat
      if (activeSessionId) {
        const summary = generatePipelineSummary(Array.from(selectedNodes));
        const aiMessage = {
          id: uuidv4(),
          content: summary,
          type: 'ai' as const,
          messageType: 'text' as const,
          role: 'assistant' as const,
          timestamp: new Date(),
        };
        
        try {
          await addMessageToSession(activeSessionId, aiMessage);
          console.log('[PipelineBlueprintDisplay] AI summary message added to chat');
        } catch (error) {
          console.error('[PipelineBlueprintDisplay] Failed to add AI summary message:', error);
          // Don't throw - this is a non-critical error
        }
      }
      
      // Call optional callback (this will update the chat message)
      if (onApprove) {
        onApprove(Array.from(selectedNodes));
      }
    } catch (error: any) {
      console.error('[PipelineBlueprintDisplay] Error approving blueprint:', error);
      
      // Revert approved state to show buttons again
      setLocalApproved(false);
      
      // Create error message for chat
      if (activeSessionId) {
        const errorDetails: ErrorDetails = {
          code: 'PIPELINE_APPROVAL_ERROR',
          category: ErrorCategory.PROCESSING,
          severity: ErrorSeverity.HIGH,
          userMessage: error.message || 'Failed to approve pipeline blueprint. Please try again.',
          technicalMessage: error.stack || error.toString(),
          context: {
            feature: 'Pipeline',
            blueprint: {
              nodeCount: localBlueprint.nodes.length,
              selectedNodeCount: selectedNodes.size,
              nodeTypes: Array.from(selectedNodes).map(id => {
                const node = localBlueprint.nodes.find(n => n.id === id);
                return node?.type;
              }),
            },
            error: error.message || error.toString(),
          },
          suggestions: [
            {
              action: 'Try Again',
              description: 'Click "Approve & Configure Parameters" again to retry',
              type: 'retry',
              autoFixable: false,
              priority: 1,
            },
            {
              action: 'Check Node Configuration',
              description: 'Ensure all required node parameters are configured correctly',
              type: 'fix',
              autoFixable: false,
              priority: 2,
            },
            {
              action: 'Contact Support',
              description: 'If the issue persists, please contact support with the error details',
              type: 'contact',
              autoFixable: false,
              priority: 3,
            },
          ],
          timestamp: new Date(),
        };
        
        const errorMessage = {
          id: uuidv4(),
          content: `An error occurred while approving the pipeline blueprint: ${errorDetails.userMessage}`,
          type: 'ai' as const,
          messageType: 'text' as const,
          role: 'assistant' as const,
          timestamp: new Date(),
          error: errorDetails,
        };
        
        try {
          await addMessageToSession(activeSessionId, errorMessage);
          console.log('[PipelineBlueprintDisplay] Error message added to chat');
        } catch (addError) {
          console.error('[PipelineBlueprintDisplay] Failed to add error message to chat:', addError);
        }
      }
    }
  };

  const handleReject = () => {
    // Hide the blueprint display immediately
    hasUserInteracted.current = true;
    setIsRejected(true);
    
    rejectBlueprint();
    if (onReject) {
      onReject();
    }
  };

  const handleNodeIconClick = (e: React.MouseEvent, node: PipelineNodeBlueprint) => {
    e.stopPropagation(); // Prevent node toggle when clicking icon
    // Allow configuration for all node types
    setConfiguringNodeId(node.id);
  };

  const handleConfigSave = (nodeId: string, config: Record<string, any>) => {
    // Update the node config in local blueprint
    setLocalBlueprint(prev => ({
      ...prev,
      nodes: prev.nodes.map(n => 
        n.id === nodeId ? { ...n, config } : n
      )
    }));
    setConfiguringNodeId(null);
  };

  // Don't render if rejected
  if (isRejected) {
    return null;
  }

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

      {localBlueprint.missing_resources && localBlueprint.missing_resources.length > 0 && (
        <div className="mb-3 p-2 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
          <strong>Missing resources:</strong> {localBlueprint.missing_resources.join(', ')}
        </div>
      )}

      <div className="mb-3">
        <div className="text-xs font-medium text-gray-700 mb-2">
          Select nodes to include ({selectedNodes.size} of {localBlueprint.nodes.length} selected):
        </div>
        <div className="space-y-2">
          {localBlueprint.nodes
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
                <div 
                  className={`${nodeColors[node.type] || 'bg-gray-500'} text-white p-1.5 rounded flex-shrink-0 cursor-pointer hover:opacity-80 transition-opacity`}
                  onClick={(e) => handleNodeIconClick(e, node)}
                  title="Click to configure parameters"
                >
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

      {localBlueprint.edges.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-medium text-gray-700 mb-2">
            Connections ({localBlueprint.edges.length}):
          </div>
          <div className="space-y-1">
            {localBlueprint.edges.map((edge, index) => {
              const sourceNode = localBlueprint.nodes.find(n => n.id === edge.source);
              const targetNode = localBlueprint.nodes.find(n => n.id === edge.target);
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
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-center space-x-2 mb-2">
            <Check className="w-5 h-5 text-green-600" />
            <span className="text-sm font-medium text-green-800">Pipeline Approved</span>
          </div>
          <p className="text-xs text-green-700 mb-3">
            Pipeline created successfully with {selectedNodes.size} node{selectedNodes.size === 1 ? '' : 's'}. 
            You can now configure parameters for each node in the pipeline canvas.
          </p>
          <button
            onClick={() => {
              setActivePane('pipeline');
              setViewerVisible(true);
            }}
            className="w-full inline-flex items-center justify-center space-x-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <Settings className="w-4 h-4" />
            <span>Open Pipeline Canvas to Configure</span>
            <ExternalLink className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Node Configuration Modal */}
      {configuringNodeId && (() => {
        const node = localBlueprint.nodes.find(n => n.id === configuringNodeId);
        if (!node) return null;
        return (
          <NodeConfigModal
            isOpen={true}
            node={node}
            onClose={() => setConfiguringNodeId(null)}
            onSave={(config) => handleConfigSave(node.id, config)}
          />
        );
      })()}
    </div>
  );
};

