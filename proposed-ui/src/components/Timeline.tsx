import { Leg } from "../types/domain";

export function Timeline(props: {
  legs: Leg[];
  activeLegId?: string;
  onSelectLeg: (legId: string) => void;
}) {
  return (
    <div className="timeline">
      {props.legs.map((l, idx) => (
        <div key={l.legId} className="timeline-item">
          <button
            type="button"
            className={props.activeLegId === l.legId ? "dot active" : "dot"}
            onClick={() => props.onSelectLeg(l.legId)}
            title={`${l.legType.toUpperCase()} ${l.side.toUpperCase()} ${l.quantity}`}
          />
          <div className="timeline-label">
            <div className="tl-top">{l.legType.toUpperCase()}</div>
            <div className="tl-sub">
              {l.side === "buy" ? "+" : "-"}
              {l.quantity} @ {l.avgPrice.toFixed(2)}
            </div>
          </div>
          {idx < props.legs.length - 1 && <div className="line" />}
        </div>
      ))}
    </div>
  );
}
