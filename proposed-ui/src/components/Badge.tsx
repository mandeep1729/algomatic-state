export function Badge(props: { text: string; tone?: "neutral" | "info" | "warn" | "danger" }) {
  const tone = props.tone ?? "neutral";
  return <span className={`badge ${tone}`}>{props.text}</span>;
}
