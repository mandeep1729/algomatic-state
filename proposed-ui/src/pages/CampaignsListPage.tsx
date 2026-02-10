import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/Card";
import { Badge } from "../components/Badge";
import { campaignSummaries } from "../data/mock";

export function CampaignsListPage() {
  const [q, setQ] = useState("");
  const nav = useNavigate();

  const items = useMemo(() => {
    const query = q.trim().toLowerCase();
    return campaignSummaries.filter((c) => c.symbol.toLowerCase().includes(query));
  }, [q]);

  return (
    <div className="stack">
      <Card
        title="Trades (Position Campaigns)"
        right={<input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search symbol…" />}
      >
        <div className="table">
          <div className="row head">
            <div>Campaign</div>
            <div>Legs</div>
            <div>Max Qty</div>
            <div>Status</div>
            <div>Evaluation</div>
          </div>

          {items.map((c) => (
            <button key={c.campaignId} className="row btnrow" onClick={() => nav(`/app/trade/${c.campaignId}`)}>
              <div>
                <div className="row-title">{c.symbol} • {c.direction.toUpperCase()}</div>
                <div className="muted small">
                  {new Date(c.openedAt).toLocaleString()} → {c.closedAt ? new Date(c.closedAt).toLocaleString() : "Open"}
                </div>
              </div>
              <div>{c.legsCount}</div>
              <div>{c.maxQty}</div>
              <div><Badge text={c.status} /></div>
              <div className="flags">
                <Badge text={c.overallLabel} tone={c.overallLabel === "fragile" ? "warn" : "neutral"} />
                {c.keyFlags.slice(0, 2).map((f) => <Badge key={f} text={f} tone="info" />)}
              </div>
            </button>
          ))}
        </div>
      </Card>
    </div>
  );
}
