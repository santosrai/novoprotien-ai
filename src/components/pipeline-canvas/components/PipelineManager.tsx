import React, { useState, useEffect } from 'react';
import { usePipelineStore } from '../store/pipelineStore';
import { usePipelineContext } from '../context/PipelineContext';
import { Pipeline } from '../types/index';
import { Trash2, Play, Edit2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Input } from './ui/input';
import { Button } from './ui/button';

interface PipelineManagerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const PipelineManager: React.FC<PipelineManagerProps> = ({ isOpen, onClose }) => {
  const { savedPipelines, loadPipeline, deletePipeline, syncPipelines } = usePipelineStore();
  const { authState, apiClient } = usePipelineContext();
  const user = authState?.user;
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');

  // Sync pipelines from backend when modal opens and user is authenticated
  useEffect(() => {
    if (isOpen && user && apiClient) {
      console.log('[PipelineManager] Syncing pipelines from backend...');
      syncPipelines({ apiClient, authState }).catch((error) => {
        console.error('[PipelineManager] Failed to sync pipelines:', error);
      });
    }
  }, [isOpen, user, apiClient, authState, syncPipelines]);

  const handleLoad = (pipeline: Pipeline) => {
    loadPipeline(pipeline.id);
    onClose();
  };

  const handleDelete = (pipelineId: string) => {
    if (confirm('Are you sure you want to delete this pipeline?')) {
      deletePipeline(pipelineId, { apiClient, authState });
    }
  };

  const handleStartEdit = (pipeline: Pipeline) => {
    setEditingId(pipeline.id);
    setEditName(pipeline.name);
  };

  const handleSaveEdit = (pipelineId: string) => {
    const pipeline = savedPipelines.find((p) => p.id === pipelineId);
    if (pipeline && editName.trim()) {
      usePipelineStore.getState().savePipeline(editName.trim(), undefined, undefined, {
        apiClient,
        authState,
      });
      setEditingId(null);
      setEditName('');
    }
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName('');
  };

  const getStatusColor = (status: Pipeline['status']) => {
    switch (status) {
      case 'running':
        return 'bg-blue-100 text-blue-800';
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Pipeline Manager</DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto">
          {savedPipelines.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 mb-2">No saved pipelines</p>
              <p className="text-sm text-gray-400">
                Create a pipeline and save it to see it here
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {savedPipelines.map((pipeline) => (
                <div
                  key={pipeline.id}
                  className="border border-gray-200 rounded-lg p-4 hover:border-gray-300 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      {editingId === pipeline.id ? (
                        <div className="flex items-center gap-2 mb-2">
                          <Input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="text-sm"
                            autoFocus
                          />
                          <Button
                            onClick={() => handleSaveEdit(pipeline.id)}
                            size="sm"
                            className="text-xs"
                          >
                            Save
                          </Button>
                          <Button
                            onClick={handleCancelEdit}
                            variant="outline"
                            size="sm"
                            className="text-xs"
                          >
                            Cancel
                          </Button>
                        </div>
                      ) : (
                        <h3 className="text-sm font-semibold text-gray-900 mb-1">
                          {pipeline.name}
                        </h3>
                      )}
                      
                      <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                        <span>{pipeline.nodes.length} nodes</span>
                        <span>•</span>
                        <span>{pipeline.edges.length} edges</span>
                        <span>•</span>
                        <span className={`px-2 py-0.5 rounded ${getStatusColor(pipeline.status)}`}>
                          {pipeline.status}
                        </span>
                      </div>
                      
                      <p className="text-xs text-gray-400">
                        Created: {new Date(pipeline.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                    
                    <div className="flex items-center gap-2 ml-4">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleLoad(pipeline)}
                        title="Load pipeline"
                      >
                        <Play className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleStartEdit(pipeline)}
                        title="Rename pipeline"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDelete(pipeline.id)}
                        title="Delete pipeline"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};





