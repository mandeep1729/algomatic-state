import { ReactNode } from "react";

export function Card(props: { title?: string; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="card">
      {(props.title || props.right) && (
        <div className="card-head">
          <div className="card-title">{props.title}</div>
          <div>{props.right}</div>
        </div>
      )}
      <div className="card-body">{props.children}</div>
    </div>
  );
}
