import React, { useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Play, RotateCcw, Copy, FileText } from 'lucide-react';
import { useAppStore } from '../stores/appStore';
import { CodeExecutor } from '../utils/codeExecutor';

const defaultCode = `// Default: Cartoon view of PDB 1CBS
try {
  await builder.loadStructure('1CBS');
  await builder.addCartoonRepresentation({ color: 'secondary-structure' });
  builder.focusView();
  console.log('Loaded 1CBS');
} catch (e) {
  console.error('Failed to load 1CBS', e);
}`;

export const CodeEditor: React.FC = () => {
  const { plugin, currentCode, setCurrentCode, isExecuting, setIsExecuting } = useAppStore();
  const editorRef = useRef<any>(null);

  useEffect(() => {
    if (!currentCode) setCurrentCode(defaultCode);
  }, [currentCode, setCurrentCode]);

  const handleEditorDidMount = (editor: any) => {
    editorRef.current = editor;
  };

  const executeCode = async () => {
    if (!currentCode.trim()) return;
    if (!plugin) {
      console.warn('[Molstar] Plugin not ready yet');
      return;
    }
    setIsExecuting(true);
    try {
      const exec = new CodeExecutor(plugin);
      const res = await exec.executeCode(currentCode);
      console.log('[Molstar] execute result:', res);
    } catch (e) {
      console.error('[Molstar] execute failed', e);
    } finally {
      setIsExecuting(false);
    }
  };

  const resetCode = () => {
    setCurrentCode(defaultCode);
  };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(currentCode);
      console.log('Code copied to clipboard');
    } catch (err) {
      console.error('Failed to copy code:', err);
    }
  };

  const loadExample = () => {
    const exampleCode = `// Example: DNA (1BNA)
try {
  await builder.loadStructure('1BNA');
  await builder.addCartoonRepresentation({ color: 'nucleotide' });
  builder.focusView();
} catch (e) { console.error(e); }`;
    setCurrentCode(exampleCode);
  };

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <div className="flex items-center space-x-2">
          <FileText className="w-4 h-4 text-gray-600" />
          <span className="text-sm font-medium text-gray-700">Molstar Code</span>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={loadExample}
            className="px-3 py-1 text-xs bg-gray-200 hover:bg-gray-300 text-gray-700 rounded"
          >
            Example
          </button>
          <button
            onClick={copyCode}
            className="p-1 text-gray-600 hover:text-gray-800"
            title="Copy code"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={resetCode}
            className="p-1 text-gray-600 hover:text-gray-800"
            title="Reset code"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <button
            onClick={executeCode}
            disabled={isExecuting}
            className="flex items-center space-x-1 px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm disabled:opacity-50"
          >
            <Play className="w-3 h-3" />
            <span>{isExecuting ? 'Running...' : 'Run'}</span>
          </button>
        </div>
      </div>

      <div className="flex-1">
        <Editor
          height="100%"
          defaultLanguage="javascript"
          value={currentCode}
          onChange={(value) => setCurrentCode(value || '')}
          onMount={handleEditorDidMount}
          theme="vs-light"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            wordWrap: 'on',
            automaticLayout: true,
            scrollBeyondLastLine: false,
            tabSize: 2,
            insertSpaces: true,
          }}
        />
      </div>
    </div>
  );
};