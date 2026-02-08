/**
 * Reusable Modal component.
 *
 * Features:
 * - Overlay with centered content
 * - Close on escape key
 * - Close on overlay click
 * - Customizable title and content
 */

import { useEffect, useRef, useCallback } from 'react';
import { X } from 'lucide-react';

export interface ModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Callback to close the modal */
  onClose: () => void;
  /** Modal title displayed in the header */
  title: string;
  /** Modal content */
  children: React.ReactNode;
  /** Optional maximum width class (default: max-w-lg) */
  maxWidth?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  maxWidth = 'max-w-lg',
}: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Handle escape key
  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    },
    [onClose]
  );

  // Handle overlay click (close when clicking outside modal content)
  const handleOverlayClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      if (event.target === overlayRef.current) {
        onClose();
      }
    },
    [onClose]
  );

  // Add/remove escape key listener
  useEffect(() => {
    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      // Prevent body scroll when modal is open
      document.body.style.overflow = 'hidden';
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
        document.body.style.overflow = '';
      };
    }
  }, [isOpen, handleKeyDown]);

  if (!isOpen) {
    return null;
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div
        ref={contentRef}
        className={`relative w-full ${maxWidth} mx-4 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] shadow-xl`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--border-color)] px-4 py-3">
          <h2
            id="modal-title"
            className="text-base font-medium text-[var(--text-primary)]"
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] transition-colors"
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[calc(100vh-200px)] overflow-y-auto">
          {children}
        </div>
      </div>
    </div>
  );
}
