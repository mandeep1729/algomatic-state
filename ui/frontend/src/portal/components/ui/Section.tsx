import { Link } from 'react-router-dom';

export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: { label: string; to: string };
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-medium">{title}</h2>
        {action && (
          <Link to={action.to} className="text-xs text-[var(--accent-blue)] hover:underline">
            {action.label}
          </Link>
        )}
      </div>
      {children}
    </div>
  );
}
