import { Card } from "../components/Card";
import { Badge } from "../components/Badge";

export function BrokersSettingsPage() {
  return (
    <div className="stack">
      <Card title="Broker Integrations" right={<Badge text="Read-only" tone="info" />}>
        <p className="muted">
          Connect your broker to sync historical executions. The platform groups them into Position Campaigns and evaluates decision points.
        </p>

        <div className="row">
          <button className="btn" type="button">Connect Broker</button>
          <button className="btn secondary" type="button">Sync Now</button>
        </div>

        <div style={{ height: 12 }} />

        <div className="table">
          <div className="row head">
            <div>Provider</div><div>Status</div><div>Last Sync</div><div>Actions</div>
          </div>
          <div className="row">
            <div>MockBroker</div>
            <div><Badge text="connected" tone="info" /></div>
            <div className="muted">Just now</div>
            <div><button className="btn secondary" type="button">Disconnect</button></div>
          </div>
        </div>
      </Card>
    </div>
  );
}
