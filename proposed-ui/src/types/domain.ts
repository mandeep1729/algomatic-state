export type Direction = "long" | "short";
export type CampaignStatus = "open" | "closed";
export type LegType = "open" | "add" | "reduce" | "close";

export type EvalScope = "campaign" | "leg" | "idea";
export type OverallLabel = "aligned" | "mixed" | "fragile" | "deviates";
export type Severity = "info" | "low" | "medium" | "high";

export type DimensionKey =
  | "regime_fit"
  | "entry_timing"
  | "exit_logic"
  | "risk_structure"
  | "behavioral"
  | "strategy_consistency";

export interface CampaignSummary {
  campaignId: string;
  symbol: string;
  direction: Direction;
  status: CampaignStatus;
  openedAt: string;
  closedAt?: string;
  legsCount: number;
  maxQty: number;
  overallLabel: OverallLabel;
  keyFlags: string[];
}

export interface Campaign {
  campaignId: string;
  symbol: string;
  direction: Direction;
  status: CampaignStatus;
  openedAt: string;
  closedAt?: string;
  legsCount: number;
  maxQty: number;
  pnlRealized?: number;
  costBasisMethod: "average" | "fifo" | "lifo";
  source: "broker_synced" | "manual" | "proposed";
}

export interface Leg {
  legId: string;
  campaignId: string;
  legType: LegType;
  side: "buy" | "sell";
  quantity: number;
  avgPrice: number;
  startedAt: string;
  endedAt: string;
}

export interface EvaluationDimension {
  dimensionKey: DimensionKey;
  severity: Severity;
  label: string;
  explanation: string;
  evidence?: Record<string, unknown>;
  visuals?: Record<string, unknown>;
}

export interface EvaluationBundle {
  bundleId: string;
  evalScope: EvalScope;
  overallLabel: OverallLabel;
  dimensions: EvaluationDimension[];
}

export interface DecisionContext {
  contextId: string;
  scope: "campaign" | "leg" | "idea";
  campaignId?: string;
  legId?: string;
  ideaId?: string;

  contextType: "entry" | "add" | "reduce" | "exit" | "post_trade_reflection";
  strategyTags: string[];
  hypothesis?: string;
  exitIntent?: "fixed" | "trail" | "scale" | "time" | "unknown";
  targetExit?: { type: "price" | "zone"; value: number | [number, number] };
  feelingsThen?: { chips: string[]; intensity?: number; note?: string };
  feelingsNow?: { chips: string[]; intensity?: number; note?: string };
  notes?: string;
  updatedAt: string;
}

export interface CampaignDetail {
  campaign: Campaign;
  legs: Leg[];
  evaluationCampaign: EvaluationBundle;
  evaluationByLeg: Record<string, EvaluationBundle>;
  contextsByLeg: Record<string, DecisionContext | undefined>;
}
