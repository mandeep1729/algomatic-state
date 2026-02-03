import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

interface ChartContextValue {
  chartActive: boolean;
  featureNames: string[];
  selectedFeatures: string[];
  setChartActive: (active: boolean) => void;
  setFeatureNames: (names: string[]) => void;
  onFeatureToggle: (key: string) => void;
}

const ChartContext = createContext<ChartContextValue | null>(null);

export function ChartProvider({ children }: { children: ReactNode }) {
  const [chartActive, setChartActive] = useState(false);
  const [featureNames, setFeatureNames] = useState<string[]>([]);
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([]);

  const onFeatureToggle = useCallback((key: string) => {
    setSelectedFeatures((prev) =>
      prev.includes(key) ? prev.filter((f) => f !== key) : [...prev, key]
    );
  }, []);

  return (
    <ChartContext.Provider
      value={{
        chartActive,
        featureNames,
        selectedFeatures,
        setChartActive,
        setFeatureNames,
        onFeatureToggle,
      }}
    >
      {children}
    </ChartContext.Provider>
  );
}

export function useChartContext() {
  const ctx = useContext(ChartContext);
  if (!ctx) throw new Error('useChartContext must be used within ChartProvider');
  return ctx;
}
