const EMOTION_OPTIONS = [
  'calm',
  'confident',
  'rushed',
  'anxious',
  'frustrated',
  'tired',
  'excited',
  'impulsive',
  'focused',
] as const;

interface EmotionChipsProps {
  value: string[];
  onChange: (v: string[]) => void;
}

export function EmotionChips({ value, onChange }: EmotionChipsProps) {
  const toggle = (emotion: string) => {
    const set = new Set(value);
    if (set.has(emotion)) {
      set.delete(emotion);
    } else {
      set.add(emotion);
    }
    onChange(Array.from(set));
  };

  return (
    <div className="flex flex-wrap gap-2">
      {EMOTION_OPTIONS.map((option) => {
        const isActive = value.includes(option);
        return (
          <button
            key={option}
            type="button"
            onClick={() => toggle(option)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              isActive
                ? 'border-[var(--accent-purple)] bg-[var(--accent-purple)]/10 text-[var(--accent-purple)]'
                : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {option}
          </button>
        );
      })}
    </div>
  );
}
