export function Tabs<T extends string>(props: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="tabs">
      {props.options.map((o) => (
        <button
          key={o.value}
          className={props.value === o.value ? "tab active" : "tab"}
          onClick={() => props.onChange(o.value)}
          type="button"
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
