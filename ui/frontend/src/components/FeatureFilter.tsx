import { useState } from 'react';
import {
  featuresConfig,
  FEATURE_CATEGORY_LABELS,
  FEATURE_CATEGORY_COLORS,
} from '../featureConfig';

interface FeatureFilterProps {
  selectedFeatures: string[];
  availableFeatures: string[];
  onFeatureToggle: (featureKey: string) => void;
}

export function FeatureFilter({
  selectedFeatures,
  availableFeatures,
  onFeatureToggle,
}: FeatureFilterProps) {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(category)) {
        next.delete(category);
      } else {
        next.add(category);
      }
      return next;
    });
  };

  // Count selected features per category
  const getSelectedCount = (category: string): number => {
    const categoryFeatures = Object.keys(featuresConfig.features[category] || {});
    return categoryFeatures.filter((f) => selectedFeatures.includes(f)).length;
  };

  // Count available features per category
  const getAvailableCount = (category: string): number => {
    const categoryFeatures = Object.keys(featuresConfig.features[category] || {});
    return categoryFeatures.filter((f) => availableFeatures.includes(f)).length;
  };

  return (
    <div className="feature-filter">
      <h3 className="section-title" style={{ marginBottom: '0.5rem' }}>
        Feature Overlays
      </h3>
      <div style={{ fontSize: '0.7rem', color: '#8b949e', marginBottom: '0.75rem' }}>
        {selectedFeatures.length} selected
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {featuresConfig.feature_categories.map((category) => {
          const isExpanded = expandedCategories.has(category);
          const categoryFeatures = featuresConfig.features[category];
          const selectedCount = getSelectedCount(category);
          const availableCount = getAvailableCount(category);
          const categoryColor = FEATURE_CATEGORY_COLORS[category] || '#58a6ff';

          if (!categoryFeatures || availableCount === 0) return null;

          return (
            <div key={category}>
              {/* Category Header */}
              <div
                onClick={() => toggleCategory(category)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.4rem 0.5rem',
                  background: isExpanded ? '#21262d' : 'transparent',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  borderLeft: `3px solid ${categoryColor}`,
                  marginLeft: '2px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{
                    fontSize: '0.7rem',
                    color: '#8b949e',
                    width: '12px',
                    textAlign: 'center',
                  }}>
                    {isExpanded ? '▼' : '▶'}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#e6edf3' }}>
                    {FEATURE_CATEGORY_LABELS[category] || category}
                  </span>
                </div>
                {selectedCount > 0 && (
                  <span style={{
                    fontSize: '0.65rem',
                    background: categoryColor,
                    color: '#fff',
                    padding: '1px 6px',
                    borderRadius: '10px',
                  }}>
                    {selectedCount}
                  </span>
                )}
              </div>

              {/* Feature Checkboxes */}
              {isExpanded && (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1px',
                  marginLeft: '20px',
                  marginTop: '2px',
                  marginBottom: '4px',
                }}>
                  {Object.entries(categoryFeatures).map(([featureKey, featureDef]) => {
                    const isAvailable = availableFeatures.includes(featureKey);
                    const isSelected = selectedFeatures.includes(featureKey);

                    if (!isAvailable) return null;

                    return (
                      <label
                        key={featureKey}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          padding: '0.25rem 0.5rem',
                          cursor: 'pointer',
                          borderRadius: '3px',
                          background: isSelected ? 'rgba(88, 166, 255, 0.1)' : 'transparent',
                        }}
                        title={featureDef.description}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => onFeatureToggle(featureKey)}
                          style={{
                            width: '14px',
                            height: '14px',
                            accentColor: categoryColor,
                            cursor: 'pointer',
                          }}
                        />
                        <span style={{
                          fontSize: '0.75rem',
                          color: isSelected ? '#e6edf3' : '#8b949e',
                        }}>
                          {featureDef.name}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {selectedFeatures.length > 0 && (
        <button
          onClick={() => selectedFeatures.forEach((f) => onFeatureToggle(f))}
          style={{
            marginTop: '0.75rem',
            padding: '0.3rem 0.6rem',
            fontSize: '0.7rem',
            background: '#21262d',
            color: '#8b949e',
            border: '1px solid #30363d',
            borderRadius: '4px',
            cursor: 'pointer',
            width: '100%',
          }}
        >
          Clear All
        </button>
      )}
    </div>
  );
}
