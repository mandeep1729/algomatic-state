/**
 * Reusable <select> with <optgroup> elements.
 */

interface GroupedOption {
  value: string;
  label: string;
  group: string;
}

interface GroupedSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: GroupedOption[];
  groupLabels: Record<string, string>;
  className?: string;
  placeholder?: string;
}

export function GroupedSelect({
  value,
  onChange,
  options,
  groupLabels,
  className = '',
  placeholder,
}: GroupedSelectProps) {
  // Group options by their group key
  const groups = new Map<string, GroupedOption[]>();
  for (const opt of options) {
    const list = groups.get(opt.group) ?? [];
    list.push(opt);
    groups.set(opt.group, list);
  }

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`form-input h-8 text-xs ${className}`}
    >
      {placeholder && <option value="">{placeholder}</option>}
      {Array.from(groups.entries()).map(([group, opts]) => (
        <optgroup key={group} label={groupLabels[group] || group}>
          {opts.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  );
}
