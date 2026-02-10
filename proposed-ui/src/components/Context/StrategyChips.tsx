const OPTIONS = ["breakout", "pullback", "momentum", "mean_reversion", "range_fade", "news", "other"] as const;

export function StrategyChips(props: { value: string[]; onChange: (v: string[]) => void }) {
  const toggle = (x: string) => {
    const set = new Set(props.value);
    set.has(x) ? set.delete(x) : set.add(x);
    props.onChange(Array.from(set));
  };

  return (
    <div className="chips">
      {OPTIONS.map((o) => (
        <button key={o} type="button" className={props.value.includes(o) ? "chip active" : "chip"} onClick={() => toggle(o)}>
          {o.replaceAll("_", " ")}
        </button>
      ))}
    </div>
  );
}
