const EMOS = ["calm", "confident", "rushed", "anxious", "frustrated", "tired", "excited", "impulsive", "focused"] as const;

export function EmotionChips(props: { value: string[]; onChange: (v: string[]) => void }) {
  const toggle = (x: string) => {
    const set = new Set(props.value);
    set.has(x) ? set.delete(x) : set.add(x);
    props.onChange(Array.from(set));
  };
  return (
    <div className="chips">
      {EMOS.map((e) => (
        <button key={e} type="button" className={props.value.includes(e) ? "chip active" : "chip"} onClick={() => toggle(e)}>
          {e}
        </button>
      ))}
    </div>
  );
}
