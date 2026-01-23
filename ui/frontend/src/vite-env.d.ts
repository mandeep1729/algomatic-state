/// <reference types="vite/client" />

declare module 'react-plotly.js' {
  import { Component } from 'react';
  import { PlotParams } from 'plotly.js';

  interface PlotProps {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    style?: React.CSSProperties;
    className?: string;
    useResizeHandler?: boolean;
    onInitialized?: (figure: Readonly<PlotParams>, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: Readonly<PlotParams>, graphDiv: HTMLElement) => void;
    onPurge?: (figure: Readonly<PlotParams>, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
  }

  export default class Plot extends Component<PlotProps> {}
}

declare namespace Plotly {
  interface Shape {
    type: 'rect' | 'circle' | 'line' | 'path';
    xref: string;
    yref: string;
    x0: string | number;
    x1: string | number;
    y0: number;
    y1: number;
    fillcolor: string;
    line: { width: number; color?: string };
    layer: 'below' | 'above';
  }
}
