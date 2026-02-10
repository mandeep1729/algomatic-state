import { Card } from "../components/Card";

export function NotFoundPage() {
  return (
    <div className="stack">
      <Card title="Not Found">
        <p className="muted">That page doesn’t exist.</p>
      </Card>
    </div>
  );
}
