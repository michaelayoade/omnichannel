import React from 'react';

/**
 * Simple tailwind-based loading spinner used during suspense states.
 * Size prop: "sm" | "md" | "lg" (default md)
 */
export default function LoadingSpinner({ size = 'md', className = '' }) {
  const sizes = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-10 w-10 border-4',
  };

  return (
    <div className={`flex items-center justify-center ${className}`} role="status">
      <span
        className={`animate-spin rounded-full border-t-transparent border-solid border-primary ${sizes[size]}`}
      />
      <span className="sr-only">Loading...</span>
    </div>
  );
}
