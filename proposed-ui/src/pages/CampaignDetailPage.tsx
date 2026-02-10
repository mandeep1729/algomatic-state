import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { Tabs } from "../components/Tabs";
import { Timeline } from "../components/Timeline";
import { EvaluationGrid } from "../components/Evaluation/EvaluationGrid";
import { ContextPanel } from "../components/Context/ContextPanel";
import { campaignDetailById } from "../data/mock";
import { DecisionContext } from "../types/domain";

type TabKey = "campaign" | string;

export function CampaignDetailPage() {
  const { campaignId } = useParams();
  const detail = campaignId ? campaignDetailById[campaignId] : undefined;

  const [tab, setTab] = useState<TabKey>("campaign");
  const [activeLegId, setActiveLegId] = useState<string | undefined>(detail?.legs[0]?.legId);

  const tabs = useMemo(() => {
    if (!detail) return [];
    return [
      { value: "campaign" as TabKey, label: "Campaign Summary" },
      ...detail.legs.map((l, idx) => ({
        value: l.legId as TabKey,
        label: `Decision: ${l.legType.toUpperCase()}${l.legType === "add" ? ` #${idx}` : ""}`,
      })),
    ];
  }, [detail]);

  const [contextsByLeg, setContextsByLeg] = useState<Record<string, DecisionContext | undefined>>(detail?.contextsByLeg ?? {});

  if (!detail) return <div className="stack"><Card title="Not found">No campaign.</Card></div>;

  const isCampaign = tab === "campaign";
  const selectedLeg = !isCampaign ? detail.legs.find((l) => l.legId === tab) : undefined;

  const dims = isCampaign
    ? detail.evaluationCampaign.dimensions
    : (selectedLeg ? detail.evaluationByLeg[selectedLeg.legId]?.dimensions ?? [] : []);

  const contextType =
    isCampaign ? "post_trade_reflection" :
    selectedLeg?.legType === "close" ? "exit" :
    selectedLeg?.legType === "reduce" ? "reduce" :
    selectedLeg?.legType === "add" ? "add" : "entry";

  return (
    <div className="stack">
      <Card
        title={`${detail.campaign.symbol} • ${detail.campaign.direction.toUpperCase()} • ${detail.campaign.legsCount} legs`}
        right={<Badge text={detail.evaluationCampaign.overallLabel} tone="neutral" />}
      >
        <div className="muted small">
          Opened {new Date(detail.campaign.openedAt).toLocaleString()} {detail.campaign.closedAt ? `• Closed ${new Date(detail.campaign.closedAt).toLocaleString()}` : "• Open"}
          {" • "}Source: {detail.campaign.source} • Cost basis: {detail.campaign.costBasisMethod}
        </div>

        <div style={{ height: 12 }} />

        <Timeline
          legs={detail.legs}
          activeLegId={activeLegId}
          onSelectLeg={(id) => {
            setActiveLegId(id);
            setTab(id);
          }}
        />

        <div style={{ height: 12 }} />
        <Tabs value={tab} options={tabs} onChange={setTab} />
      </Card>

      <div className="grid2">
        <Card title={isCampaign ? "Evaluation (Campaign)" : `Evaluation (Decision: ${selectedLeg?.legType.toUpperCase()})`}>
          <EvaluationGrid dims={dims} />
        </Card>

        <ContextPanel
          title={isCampaign ? "Context (Campaign-level)" : "Context (This decision point)"}
          scope={isCampaign ? "campaign" : "leg"}
          contextType={contextType}
          campaignId={detail.campaign.campaignId}
          legId={selectedLeg?.legId}
          initial={selectedLeg ? contextsByLeg[selectedLeg.legId] : undefined}
          onAutosave={(next) => {
            if (!selectedLeg) return;
            setContextsByLeg((m) => ({ ...m, [selectedLeg.legId]: next }));
          }}
        />
      </div>
    </div>
  );
}
