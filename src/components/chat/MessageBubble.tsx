import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  AlphaFoldResultCard,
  SmilesResultCard,
  OpenFold2ResultCard,
  DiffDockResultCard,
  RFdiffusionResultCard,
  ProteinMPNNResultCard,
  FileAttachmentCard,
  PipelineAttachmentCard,
} from './results';
import { AgentPill } from '../AgentPill';
import { ToolPill } from '../ToolPill';
import { ThinkingProcessDisplay } from '../ThinkingProcessDisplay';
import { JobLoadingPill } from '../JobLoadingPill';
import { PipelineBlueprintDisplay } from '../PipelineBlueprintDisplay';
import ValidationPanel from '../ValidationPanel';
import { ErrorDisplay } from '../ErrorDisplay';
import { RFdiffusionErrorHandler } from '../../utils/errorHandler';
import type { ExtendedMessage } from '../../types/chat';
import type { ValidationReport } from '../../types/validation';

interface MessageBubbleProps {
  message: ExtendedMessage;
  messages: ExtendedMessage[];
  plugin: any;
  activeSession: { id: string; messages: any[] } | null;
  updateMessages: (msgs: any[]) => void;
  setCurrentCode: (code: string) => void;
  setPendingCodeToRun: (code: string) => void;
  onLoadAlphaFoldInViewer: (result: any, message?: any) => void;
  onLoadSmilesInViewer: (result: any, message?: any) => void;
  onDownloadSmiles: (result: any) => void;
  onLoadOpenFold2InViewer: (result: any, message?: any) => void;
  onLoadDiffDockInViewer: (result: any, message?: any) => void;
  onLoadRFdiffusionInViewer: (result: any, message?: any) => void;
  onLoadFileInViewer: (fileInfo: any) => void;
  onValidateStructure: (pdbContent: string) => void;
  onRetryAlphaFold: (sequence: string, parameters: any) => void;
  setGhostBlueprint: (blueprint: any) => void;
  isValidUploadedFile: (fileInfo: any) => boolean;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  messages,
  plugin,
  activeSession,
  updateMessages,
  setCurrentCode,
  setPendingCodeToRun,
  onLoadAlphaFoldInViewer,
  onLoadSmilesInViewer,
  onDownloadSmiles,
  onLoadOpenFold2InViewer,
  onLoadDiffDockInViewer,
  onLoadRFdiffusionInViewer,
  onLoadFileInViewer,
  onValidateStructure,
  onRetryAlphaFold,
  isValidUploadedFile,
}) => {
  const renderMessageContent = (content: string) => {
    try {
      const parsed = JSON.parse(content);
      return (
        <pre className="text-[10px] whitespace-pre-wrap bg-white border border-gray-200 rounded p-1.5 overflow-x-auto leading-relaxed">
          {JSON.stringify(parsed, null, 2)}
        </pre>
      );
    } catch {
      // not JSON
    }

    return (
      <div className="markdown-content text-sm leading-relaxed [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:mt-2 [&_h1]:mb-1 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-2 [&_h2]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:mt-1.5 [&_h3]:mb-0.5 [&_p]:my-1 [&_p]:whitespace-pre-wrap [&_ul]:my-1 [&_ul]:pl-5 [&_ol]:my-1 [&_ol]:pl-5 [&_strong]:font-semibold [&_table]:w-full [&_table]:border-collapse [&_table]:border [&_table]:border-gray-200 [&_th]:text-left [&_th]:px-2 [&_th]:py-1 [&_th]:border [&_th]:border-gray-200 [&_th]:bg-gray-50 [&_td]:px-2 [&_td]:py-1 [&_td]:border [&_td]:border-gray-200 [&_tr:nth-child(even)]:bg-gray-50">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
    );
  };

  const renderValidationResult = (report: ValidationReport) => (
    <div className="mt-3 rounded-lg overflow-hidden border border-indigo-200 bg-gradient-to-br from-indigo-50 to-purple-50 p-4">
      <ValidationPanel
        report={report}
        onColorByConfidence={() => {
          const code = `
async function colorByConfidence() {
  const data = plugin.managers.structure.hierarchy.current.structures;
  if (data.length > 0) {
    const struct = data[0];
    await plugin.builders.structure.representation.addRepresentation(struct.cell.obj?.data, {
      type: 'cartoon',
      color: 'uncertainty',
    });
  }
}
colorByConfidence();`;
          setCurrentCode(code);
          setPendingCodeToRun(code);
        }}
      />
    </div>
  );

  return (
    <div
      className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-[85%] p-2 rounded-lg ${
          message.type === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        {message.type === 'ai' ? (
          <>
            {((message as ExtendedMessage).agentId || (message as ExtendedMessage).toolsInvoked?.length) && (
              <div className="flex flex-wrap items-center gap-1 mb-1.5">
                {(message as ExtendedMessage).agentId && (
                  <AgentPill agentId={(message as ExtendedMessage).agentId!} />
                )}
                {(message as ExtendedMessage).toolsInvoked?.map((tool) => (
                  <ToolPill key={tool} toolName={tool} />
                ))}
              </div>
            )}
            {message.thinkingProcess && (
              <ThinkingProcessDisplay
                thinkingSteps={message.thinkingProcess.steps}
                isProcessing={!message.thinkingProcess.isComplete}
                currentStep={message.thinkingProcess.steps.findIndex(s => s.status === 'processing') + 1}
              />
            )}
            {message.jobId && message.jobType && (
              <JobLoadingPill
                message={message}
                onJobComplete={(data: any) => {
                  if (activeSession) {
                    const msgs = activeSession.messages || [];
                    const messageIndex = msgs.findIndex((m: any) => m.id === message.id);
                    if (messageIndex !== -1) {
                      const updatedMessages = [...msgs];
                      updatedMessages[messageIndex] = {
                        ...updatedMessages[messageIndex],
                        content: `RFdiffusion protein design completed successfully! The designed structure is ready for download and visualization.`,
                        rfdiffusionResult: {
                          pdbContent: data.pdbContent,
                          filename: data.filename || `designed_${Date.now()}.pdb`,
                          parameters: data.parameters,
                          metadata: data.metadata
                        },
                        jobId: undefined,
                        jobType: undefined
                      };
                      updateMessages(updatedMessages);
                    }
                  }
                }}
                onJobError={(error: string, errorData?: any) => {
                  if (activeSession) {
                    const msgs = activeSession.messages || [];
                    const messageIndex = msgs.findIndex((m: any) => m.id === message.id);
                    if (messageIndex !== -1) {
                      const structuredError = errorData?.errorCode
                        ? RFdiffusionErrorHandler.handleError(errorData, { jobId: message.jobId, feature: 'RFdiffusion' })
                        : RFdiffusionErrorHandler.handleError(error, { jobId: message.jobId, feature: 'RFdiffusion' });
                      
                      const displayContent = errorData?.aiSummary || structuredError.userMessage || error;
                      
                      const updatedMessages = [...msgs];
                      updatedMessages[messageIndex] = {
                        ...updatedMessages[messageIndex],
                        content: displayContent,
                        error: structuredError,
                        jobId: undefined,
                        jobType: undefined
                      };
                      updateMessages(updatedMessages);
                    }
                  }
                }}
              />
            )}
            {renderMessageContent(message.content)}
            {message.blueprint && (
              <div className="mt-3">
                <PipelineBlueprintDisplay
                  blueprint={message.blueprint}
                  rationale={message.blueprintRationale}
                  isApproved={message.blueprintApproved || false}
                  onApprove={(selectedNodeIds) => {
                    console.log('[ChatPanel] Blueprint approved with nodes:', selectedNodeIds);
                    
                    if (activeSession) {
                      const msgs = activeSession.messages || [];
                      const messageIndex = msgs.findIndex((m: any) => m.id === message.id);
                      if (messageIndex !== -1) {
                        const updatedMessages = [...msgs];
                        updatedMessages[messageIndex] = {
                          ...updatedMessages[messageIndex],
                          blueprintApproved: true,
                          content: `Pipeline blueprint approved! Created pipeline with ${selectedNodeIds.length} node${selectedNodeIds.length === 1 ? '' : 's'}. You can now configure parameters in the pipeline canvas.`,
                        } as ExtendedMessage;
                        updateMessages(updatedMessages);
                      }
                    }
                  }}
                  onReject={() => {
                    console.log('[ChatPanel] Blueprint rejected');
                    
                    if (activeSession) {
                      const msgs = activeSession.messages || [];
                      const messageIndex = msgs.findIndex((m: any) => m.id === message.id);
                      if (messageIndex !== -1) {
                        const updatedMessages = [...msgs];
                        updatedMessages[messageIndex] = {
                          ...updatedMessages[messageIndex],
                          blueprintApproved: false,
                          content: message.content + '\n\nPipeline blueprint rejected.',
                        } as ExtendedMessage;
                        updateMessages(updatedMessages);
                      }
                    }
                  }}
                />
              </div>
            )}
            {(() => {
              const messageIndex = messages.findIndex(m => m.id === message.id);
              if (messageIndex <= 0) return null;
              
              const prevMsg = messages[messageIndex - 1];
              if (prevMsg.type === 'user' && prevMsg.uploadedFile && isValidUploadedFile(prevMsg.uploadedFile)) {
                return (
                  <div className="mt-3">
                    <FileAttachmentCard
                      fileInfo={prevMsg.uploadedFile}
                      isUserMessage={false}
                      onLoadInViewer={onLoadFileInViewer}
                    />
                  </div>
                );
              }
              return null;
            })()}
            <AlphaFoldResultCard
              result={message.alphafoldResult}
              plugin={plugin}
              onLoadInViewer={onLoadAlphaFoldInViewer}
              onValidate={onValidateStructure}
              message={message}
            />
            <SmilesResultCard
              result={message.smilesResult}
              plugin={plugin}
              onLoadInViewer={() => onLoadSmilesInViewer(message.smilesResult, message)}
              onDownload={() => onDownloadSmiles(message.smilesResult)}
            />
            <OpenFold2ResultCard
              result={message.openfold2Result}
              plugin={plugin}
              onLoadInViewer={() => onLoadOpenFold2InViewer(message.openfold2Result, message)}
              onValidate={onValidateStructure}
            />
            <DiffDockResultCard
              result={message.diffdockResult}
              plugin={plugin}
              onLoadInViewer={() => onLoadDiffDockInViewer(message.diffdockResult, message)}
            />
            <RFdiffusionResultCard
              result={message.rfdiffusionResult}
              plugin={plugin}
              onLoadInViewer={() => onLoadRFdiffusionInViewer(message.rfdiffusionResult, message)}
            />
            <ProteinMPNNResultCard result={message.proteinmpnnResult} />
            {message.validationResult && renderValidationResult(message.validationResult)}
            {message.error && (
              <div className="mt-3">
                <ErrorDisplay 
                  error={message.error}
                  onRetry={() => {
                    if (message.error?.context?.sequence && message.error?.context?.parameters) {
                      onRetryAlphaFold(
                        message.error.context.sequence, 
                        message.error.context.parameters
                      );
                    }
                  }}
                />
              </div>
            )}
          </>
        ) : (
          <>
            <p className="text-sm leading-relaxed">{message.content}</p>
            {message.uploadedFile && isValidUploadedFile(message.uploadedFile) && (
              <div className="mt-1.5">
                <FileAttachmentCard
                  fileInfo={message.uploadedFile}
                  isUserMessage={true}
                  onLoadInViewer={onLoadFileInViewer}
                />
              </div>
            )}
            {message.pipeline && (
              <div className="mt-1.5">
                <PipelineAttachmentCard
                  pipeline={message.pipeline}
                  isUserMessage={true}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
