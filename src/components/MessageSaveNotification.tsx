import React, { useState, useEffect } from 'react';
import { AlertCircle, X, CheckCircle2, RefreshCw } from 'lucide-react';
import { useChatHistoryStore } from '../stores/chatHistoryStore';

export const MessageSaveNotification: React.FC = () => {
  const [showFailed, setShowFailed] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [successCount, setSuccessCount] = useState(0);
  const { getPendingMessageCount, retryPendingMessages } = useChatHistoryStore();
  
  useEffect(() => {
    const handleSaveFailed = () => {
      setShowFailed(true);
      // Auto-hide after 5 seconds
      setTimeout(() => setShowFailed(false), 5000);
    };
    
    const handleMessagesSaved = (event: CustomEvent) => {
      setSuccessCount(event.detail.count || 1);
      setShowSuccess(true);
      // Auto-hide after 3 seconds
      setTimeout(() => setShowSuccess(false), 3000);
    };
    
    window.addEventListener('message-save-failed', handleSaveFailed as EventListener);
    window.addEventListener('messages-saved', handleMessagesSaved as EventListener);
    
    // Check for pending messages on mount
    const pendingCount = getPendingMessageCount();
    if (pendingCount > 0) {
      setShowFailed(true);
    }
    
    return () => {
      window.removeEventListener('message-save-failed', handleSaveFailed as EventListener);
      window.removeEventListener('messages-saved', handleMessagesSaved as EventListener);
    };
  }, [getPendingMessageCount]);
  
  const handleRetry = async () => {
    try {
      await retryPendingMessages();
    } catch (error) {
      console.error('Failed to retry pending messages:', error);
    }
  };
  
  const pendingCount = getPendingMessageCount();
  
  if (!showFailed && !showSuccess && pendingCount === 0) {
    return null;
  }
  
  return (
    <>
      {showFailed && pendingCount > 0 && (
        <div className="fixed bottom-4 right-4 z-50 max-w-md">
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg shadow-lg p-4 flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-yellow-800 mb-1">
                Messages Not Saved
              </h4>
              <p className="text-sm text-yellow-700 mb-2">
                {pendingCount} message{pendingCount !== 1 ? 's' : ''} failed to save to the database. They will be retried automatically.
              </p>
              <div className="flex items-center space-x-2">
                <button
                  onClick={handleRetry}
                  className="inline-flex items-center space-x-1 px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-medium rounded transition-colors"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Retry Now</span>
                </button>
                <button
                  onClick={() => setShowFailed(false)}
                  className="text-yellow-600 hover:text-yellow-800 text-xs"
                >
                  Dismiss
                </button>
              </div>
            </div>
            <button
              onClick={() => setShowFailed(false)}
              className="text-yellow-400 hover:text-yellow-600 flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
      
      {showSuccess && (
        <div className="fixed bottom-4 right-4 z-50 max-w-md">
          <div className="bg-green-50 border border-green-200 rounded-lg shadow-lg p-4 flex items-start space-x-3">
            <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <h4 className="text-sm font-medium text-green-800 mb-1">
                Messages Saved
              </h4>
              <p className="text-sm text-green-700">
                {successCount} message{successCount !== 1 ? 's' : ''} successfully saved to the database.
              </p>
            </div>
            <button
              onClick={() => setShowSuccess(false)}
              className="text-green-400 hover:text-green-600 flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
};
