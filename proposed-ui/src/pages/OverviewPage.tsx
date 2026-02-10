import { Card } from "../components/Card";

export function OverviewPage() {
  return (
    <div className="stack">
      <Card title="Overview">
        <p className="muted">
          This portal groups executions into <b>Position Campaigns</b> and evaluates decision points (open/add/reduce/close).
        </p>
      </Card>
      <Card title="Next">
        <ul>
          <li>Go to Trades to view campaigns</li>
          <li>Use Evaluate to evaluate a proposed trade idea</li>
          <li>Connect brokers from Brokers</li>
        </ul>
      </Card>
    </div>
  );
}
