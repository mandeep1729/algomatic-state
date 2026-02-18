/**
 * ChartHelp — collapsible "What / How / Click Actions" explainer for chart sections.
 */

import { useState } from 'react';
import { HelpCircle, ChevronDown, ChevronUp } from 'lucide-react';

interface ChartHelpProps {
  what: string;
  how: string;
  click: string;
}

export function ChartHelp({ what, how, click }: ChartHelpProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-[var(--text-secondary)] hover:text-[var(--accent-blue)]"
      >
        <HelpCircle size={12} />
        <span>What does this mean?</span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 rounded-md bg-[var(--bg-tertiary)]/50 p-3 text-xs text-[var(--text-secondary)]">
          <div><strong className="text-[var(--text-primary)]">What it shows:</strong> {what}</div>
          <div><strong className="text-[var(--text-primary)]">How to use it:</strong> {how}</div>
          <div><strong className="text-[var(--text-primary)]">Click actions:</strong> {click}</div>
        </div>
      )}
    </div>
  );
}
