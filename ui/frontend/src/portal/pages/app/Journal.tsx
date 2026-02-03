import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Smile, Meh, Frown, Angry, Plus, X, BookOpen } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import api from '../../api';
import type { JournalEntry, JournalEntryCreate, JournalEntryType, Mood, BehavioralTag, TradeSummary } from '../../types';
import { format } from 'date-fns';

const MOODS: { value: Mood; label: string; Icon: LucideIcon; color: string }[] = [
  { value: 'confident', label: 'Confident', Icon: Smile, color: 'text-[var(--accent-green)]' },
  { value: 'neutral', label: 'Neutral', Icon: Meh, color: 'text-[var(--accent-blue)]' },
  { value: 'anxious', label: 'Anxious', Icon: Frown, color: 'text-[var(--accent-yellow)]' },
  { value: 'frustrated', label: 'Frustrated', Icon: Angry, color: 'text-[var(--accent-red)]' },
];

const ENTRY_TYPES: { value: JournalEntryType; label: string }[] = [
  { value: 'daily_reflection', label: 'Daily Reflection' },
  { value: 'trade_note', label: 'Trade Note' },
];

export default function Journal() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [tags, setTags] = useState<BehavioralTag[]>([]);
  const [trades, setTrades] = useState<TradeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Filters
  const [filterType, setFilterType] = useState<JournalEntryType | ''>('');
  const [filterTag, setFilterTag] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const [entriesRes, tagsRes, tradesRes] = await Promise.all([
          api.fetchJournalEntries(),
          api.fetchBehavioralTags(),
          api.fetchTrades({ limit: 50, sort: '-entry_time' }),
        ]);
        setEntries(entriesRes);
        setTags(tagsRes);
        setTrades(tradesRes.trades);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Apply filters
  const filtered = entries.filter((e) => {
    if (filterType && e.type !== filterType) return false;
    if (filterTag && !e.tags.includes(filterTag)) return false;
    return true;
  });

  // All unique tags from entries for the filter dropdown
  const allUsedTags = [...new Set(entries.flatMap((e) => e.tags))].sort();

  function handleCreated(entry: JournalEntry) {
    setEntries((prev) => [entry, ...prev]);
    setShowForm(false);
  }

  if (loading) {
    return <div className="p-8 text-[var(--text-secondary)]">Loading...</div>;
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen size={22} className="text-[var(--accent-blue)]" />
          <h1 className="text-2xl font-semibold">Journal</h1>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {showForm ? <><X size={14} /> Cancel</> : <><Plus size={14} /> New Entry</>}
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="mb-6">
          <CreateEntryForm tags={tags} trades={trades} onCreated={handleCreated} />
        </div>
      )}

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as JournalEntryType | '')}
          className="form-input w-auto"
        >
          <option value="">All types</option>
          {ENTRY_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select
          value={filterTag}
          onChange={(e) => setFilterTag(e.target.value)}
          className="form-input w-auto"
        >
          <option value="">All tags</option>
          {allUsedTags.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        {(filterType || filterTag) && (
          <button
            onClick={() => { setFilterType(''); setFilterTag(''); }}
            className="text-xs text-[var(--accent-blue)] hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Entries list */}
      <div className="space-y-4">
        {filtered.map((entry) => (
          <EntryCard key={entry.id} entry={entry} />
        ))}
        {filtered.length === 0 && (
          <div className="rounded-lg border border-dashed border-[var(--border-color)] bg-[var(--bg-secondary)] py-12 text-center text-sm text-[var(--text-secondary)]">
            {entries.length === 0
              ? 'No journal entries yet. Start by creating your first entry.'
              : 'No entries match the current filters.'}
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Entry Card
// =============================================================================

function EntryCard({ entry }: { entry: JournalEntry }) {
  const moodInfo = MOODS.find((m) => m.value === entry.mood);
  const typeLabel = ENTRY_TYPES.find((t) => t.value === entry.type)?.label ?? entry.type;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
      {/* Header */}
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">{format(new Date(entry.created_at), 'MMM d, yyyy')}</span>
          <span className={`rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
            entry.type === 'daily_reflection'
              ? 'bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
              : 'bg-[var(--accent-green)]/10 text-[var(--accent-green)]'
          }`}>
            {typeLabel}
          </span>
          {entry.trade_id && (
            <Link
              to={`/app/trades/${entry.trade_id}`}
              className="text-xs text-[var(--accent-blue)] hover:underline"
            >
              Linked trade
            </Link>
          )}
        </div>
        {moodInfo && (
          <span className={`inline-flex items-center gap-1 text-xs ${moodInfo.color}`} title={moodInfo.label}>
            <moodInfo.Icon size={14} />
            {moodInfo.label}
          </span>
        )}
      </div>

      {/* Content */}
      <p className="text-sm leading-relaxed text-[var(--text-primary)]">{entry.content}</p>

      {/* Tags */}
      {entry.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {entry.tags.map((tag) => (
            <span
              key={tag}
              className="rounded bg-[var(--bg-primary)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]"
            >
              {tag.replace(/_/g, ' ')}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Create Entry Form
// =============================================================================

function CreateEntryForm({
  tags,
  trades,
  onCreated,
}: {
  tags: BehavioralTag[];
  trades: TradeSummary[];
  onCreated: (entry: JournalEntry) => void;
}) {
  const [type, setType] = useState<JournalEntryType>('daily_reflection');
  const [content, setContent] = useState('');
  const [mood, setMood] = useState<Mood | ''>('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [tradeId, setTradeId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Group tags by category
  const tagsByCategory = tags.reduce<Record<string, BehavioralTag[]>>((acc, tag) => {
    (acc[tag.category] ??= []).push(tag);
    return acc;
  }, {});

  function toggleTag(name: string) {
    setSelectedTags((prev) =>
      prev.includes(name) ? prev.filter((t) => t !== name) : [...prev, name]
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!content.trim()) {
      setError('Content is required');
      return;
    }

    setSubmitting(true);
    try {
      const payload: JournalEntryCreate = {
        date: new Date().toISOString().slice(0, 10),
        type,
        content: content.trim(),
        tags: selectedTags.length > 0 ? selectedTags : undefined,
        mood: mood || undefined,
        trade_id: tradeId || undefined,
      };
      const created = await api.createJournalEntry(payload);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create entry');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4 space-y-4">
      <h2 className="text-lg font-medium">New Journal Entry</h2>

      {/* Type */}
      <div className="flex gap-2">
        {ENTRY_TYPES.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setType(t.value)}
            className={`rounded-md border px-3 py-2 text-sm font-medium transition-colors ${
              type === t.value
                ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Content</label>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={type === 'daily_reflection' ? 'How was your trading day? What went well? What could improve?' : 'Notes about a specific trade...'}
          rows={4}
          className="form-input resize-none"
        />
      </div>

      {/* Mood */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Mood (optional)</label>
        <div className="flex gap-2">
          {MOODS.map((m) => (
            <button
              key={m.value}
              type="button"
              onClick={() => setMood(mood === m.value ? '' : m.value)}
              className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-2 text-sm transition-colors ${
                mood === m.value
                  ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`}
              title={m.label}
            >
              <m.Icon size={15} className={mood === m.value ? m.color : ''} />
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Trade link (for trade notes) */}
      {type === 'trade_note' && (
        <div>
          <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Link to Trade (optional)</label>
          <select
            value={tradeId}
            onChange={(e) => setTradeId(e.target.value)}
            className="form-input"
          >
            <option value="">No linked trade</option>
            {trades.map((t) => (
              <option key={t.id} value={t.id}>
                {t.symbol} {t.direction.toUpperCase()} — {format(new Date(t.entry_time), 'MMM d')}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Tags */}
      <div>
        <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">Tags (optional)</label>
        <div className="space-y-2">
          {Object.entries(tagsByCategory).map(([category, catTags]) => (
            <div key={category}>
              <div className="mb-1 text-[10px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">{category}</div>
              <div className="flex flex-wrap gap-1.5">
                {catTags.map((tag) => (
                  <button
                    key={tag.name}
                    type="button"
                    onClick={() => toggleTag(tag.name)}
                    title={tag.description}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      selectedTags.includes(tag.name)
                        ? 'border-[var(--accent-blue)] bg-[var(--accent-blue)]/10 text-[var(--accent-blue)]'
                        : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                    }`}
                  >
                    {tag.name.replace(/_/g, ' ')}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-md border border-[var(--accent-red)] bg-[var(--accent-red)]/5 px-3 py-2 text-xs text-[var(--accent-red)]">
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={submitting}
        className="rounded-md bg-[var(--accent-blue)] px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? 'Saving...' : 'Save Entry'}
      </button>
    </form>
  );
}
