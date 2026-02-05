import React from 'react';
import { useAuthStore } from '../../stores/authStore';

export const CreditDisplay: React.FC = () => {
  const user = useAuthStore((state) => state.user);

  if (!user) {
    return null;
  }

  return (
    <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-indigo-100 rounded-full">
      <svg
        className="w-4 h-4 text-indigo-600 fill-current"
        viewBox="0 0 24 24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
      </svg>
      <span className="text-sm font-semibold text-indigo-900">
        {user.credits}
      </span>
    </div>
  );
};

