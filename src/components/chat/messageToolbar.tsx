import React from 'react';
import { Coins, Copy, RotateCcw } from 'lucide-react';
import type { ExtendedMessage } from '../../types/chat';

interface MessageToolbarProps {
  message: ExtendedMessage;
  isCopying: boolean;
  isRetrying: boolean;
  onCopy: () => void | Promise<void>;
  onRetry: () => void | Promise<void>;
}

function formatTokenCount(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

const MessageToolbar: React.FC<MessageToolbarProps> = ({
  message,
  isCopying,
  isRetrying,
  onCopy,
  onRetry,
}) => {
  const tokenUsage = message.tokenUsage;
  const isAiMessage = message.type === 'ai';

  return (
    <div
      className={`absolute bottom-1 right-1 inline-flex items-center gap-1 rounded-md px-1 py-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 ${
        message.type === 'user' ? 'bg-blue-500/80' : 'bg-white/90'
      }`}
    >
      {isAiMessage && tokenUsage && (
        <span
          className="inline-flex items-center gap-1 rounded-full bg-gray-200 text-gray-700 px-2 py-0.5 text-[10px]"
          title={`Input: ${tokenUsage.inputTokens} | Output: ${tokenUsage.outputTokens} | Total: ${tokenUsage.totalTokens}`}
        >
          <Coins className="w-3 h-3" />
          <span>In {formatTokenCount(tokenUsage.inputTokens)}</span>
          <span>Out {formatTokenCount(tokenUsage.outputTokens)}</span>
        </span>
      )}
      <button
        type="button"
        onClick={() => { void onCopy(); }}
        className={`inline-flex items-center justify-center w-6 h-6 rounded-md transition-colors ${
          message.type === 'user'
            ? 'text-blue-100 hover:text-white hover:bg-blue-400/70'
            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-200'
        }`}
        title={isCopying ? 'Copied' : 'Copy message'}
      >
        <Copy className="w-3.5 h-3.5" />
      </button>
      {isAiMessage && (
        <button
          type="button"
          onClick={() => { void onRetry(); }}
          disabled={isRetrying}
          className="inline-flex items-center justify-center w-6 h-6 rounded-md text-gray-500 hover:text-gray-700 hover:bg-gray-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Retry message"
        >
          <RotateCcw className={`w-3.5 h-3.5 ${isRetrying ? 'animate-spin' : ''}`} />
        </button>
      )}
    </div>
  );
};

export default MessageToolbar;
