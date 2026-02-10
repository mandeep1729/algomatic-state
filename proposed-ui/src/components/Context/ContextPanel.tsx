import { useEffect, useMemo, useState } from "react";
import { DecisionContext } from "../../types/domain";
import { StrategyChips } from "./StrategyChips";
import { EmotionChips } from "./EmotionChips";
import { Card } from "../Card";

type Draft = {
  strategyTags: string[];
  hypothesis: string;
  exitIntent: DecisionContext["exitIntent"];
  feelingsThenChips: string[];
  feelingsThenIntensity: number;
  notes: string;
};

export function ContextPanel(props: {
  title: string;
  initial?: DecisionContext;
  onAutosave: (next: DecisionContext) => void;
  scope: DecisionContext["scope"];
  contextType: DecisionContext["contextType"];
  campaignId?: string;
  legId?: string;
}) {
  const initialDraft: Draft = useMemo(() => {
    return {
      strategyTags: props.initial?.strategyTags ?? [],
      hypothesis: props.initial?.hypothesis ?? "",
      exitIntent: props.initial?.exitIntent ?? "unknown",
      feelingsThenChips: props.initial?.feelingsThen?.chips ?? [],
      feelingsThenIntensity: props.initial?.feelingsThen?.intensity ?? 2,
      notes: props.initial?.notes ?? "",
    };
  }, [props.initial]);

  const [draft, setDraft] = useState<Draft>(initialDraft);

  useEffect(() => setDraft(initialDraft), [initialDraft]);

  useEffect(() => {
    const t = setTimeout(() => {
      const next: DecisionContext = {
        contextId: props.initial?.contextId ?? crypto.randomUUID(),
        scope: props.scope,
        contextType: props.contextType,
        campaignId: props.campaignId,
        legId: props.legId,
        strategyTags: draft.strategyTags,
        hypothesis: draft.hypothesis.trim() || undefined,
        exitIntent: draft.exitIntent,
        feelingsThen: { chips: draft.feelingsThenChips, intensity: draft.feelingsThenIntensity },
        notes: draft.notes.trim() || undefined,
        updatedAt: new Date().toISOString(),
      };
      props.onAutosave(next);
    }, 600);

    return () => clearTimeout(t);
  }, [draft, props]);

  return (
    <Card title={props.title} right={<span className="muted">Autosaves</span>}>
      <div className="field">
        <label>Strategy tags</label>
        <StrategyChips value={draft.strategyTags} onChange={(v) => setDraft((d) => ({ ...d, strategyTags: v }))} />
      </div>

      <div className="field">
        <label>Hypothesis (what must be true)</label>
        <textarea
          value={draft.hypothesis}
          onChange={(e) => setDraft((d) => ({ ...d, hypothesis: e.target.value }))}
          placeholder="One or two sentences is enough…"
        />
      </div>

      <div className="field">
        <label>Exit intent</label>
        <select value={draft.exitIntent} onChange={(e) => setDraft((d) => ({ ...d, exitIntent: e.target.value as any }))}>
          <option value="unknown">Unknown</option>
          <option value="fixed">Fixed target</option>
          <option value="trail">Trailing</option>
          <option value="scale">Scale out</option>
          <option value="time">Time-based</option>
        </select>
      </div>

      <div className="field">
        <label>Feelings at decision</label>
        <EmotionChips value={draft.feelingsThenChips} onChange={(v) => setDraft((d) => ({ ...d, feelingsThenChips: v }))} />
        <div className="row">
          <span className="muted">Intensity</span>
          <input
            type="range"
            min={0}
            max={5}
            value={draft.feelingsThenIntensity}
            onChange={(e) => setDraft((d) => ({ ...d, feelingsThenIntensity: Number(e.target.value) }))}
          />
          <span className="muted">{draft.feelingsThenIntensity}</span>
        </div>
      </div>

      <div className="field">
        <label>Notes (optional)</label>
        <textarea value={draft.notes} onChange={(e) => setDraft((d) => ({ ...d, notes: e.target.value }))} placeholder="Anything else worth noting…" />
      </div>
    </Card>
  );
}
