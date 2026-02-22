export interface WelcomeScreenProps {
  isLoading: boolean;
}

export function WelcomeScreen({ isLoading }: WelcomeScreenProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4">
      {isLoading ? (
        <div className="flex items-center gap-2.5">
          <div className="flex space-x-1">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></div>
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }}></div>
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }}></div>
          </div>
          <span className="text-sm text-gray-500 animate-pulse">Thinking...</span>
        </div>
      ) : (
        <h1 className="text-3xl font-bold text-gray-900 mb-8 text-center">
          What can I do for you?
        </h1>
      )}
    </div>
  );
}
