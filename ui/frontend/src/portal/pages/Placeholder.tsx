// Generic placeholder page used for routes not yet implemented.
// Each page will be replaced with a real implementation in later steps.

interface PlaceholderProps {
  title: string;
  description?: string;
}

export default function Placeholder({ title, description }: PlaceholderProps) {
  return (
    <div className="p-8">
      <h1 className="mb-2 text-2xl font-semibold">{title}</h1>
      {description && (
        <p className="text-[var(--text-secondary)]">{description}</p>
      )}
      <div className="mt-6 rounded border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] p-12 text-center text-sm text-[var(--text-secondary)]">
        This page will be built in an upcoming step.
      </div>
    </div>
  );
}
