# Regime State Visualization UI

A React-based interactive UI for visualizing learned market regime states from OHLCV data.

## Overview

This application allows you to:
- Load market data from local CSV files or Alpaca API
- Visualize price charts with regime state overlays
- Explore computed features (returns, volatility, volume indicators)
- Analyze regime performance and transition probabilities
- View comprehensive statistics for data and learned features

## Architecture

```
ui/
├── backend/                 # Python FastAPI server
│   ├── api.py              # REST API endpoints
│   ├── requirements.txt    # Python dependencies
│   └── __init__.py
├── frontend/               # React + TypeScript application
│   ├── src/
│   │   ├── App.tsx        # Main application component
│   │   ├── api.ts         # API client functions
│   │   ├── types.ts       # TypeScript interfaces
│   │   ├── index.css      # Styling (dark theme)
│   │   ├── main.tsx       # Entry point
│   │   └── vite-env.d.ts  # Type declarations
│   ├── package.json       # Node dependencies
│   ├── vite.config.ts     # Vite configuration
│   ├── tsconfig.json      # TypeScript config
│   └── index.html
├── start_ui.bat           # Windows startup script
├── start_ui.sh            # Unix startup script
├── run_backend.py         # Backend runner script
└── README.md              # This file
```

## Prerequisites

- Python 3.10+ with virtual environment
- Node.js 18+ and npm
- Project dependencies installed (`pip install -r requirements.txt`)

## Installation

### 1. Install Backend Dependencies

```bash
# From project root, activate your virtual environment
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

# Install UI dependencies
pip install fastapi uvicorn scikit-learn joblib
```

### 2. Install Frontend Dependencies

```bash
cd ui/frontend
npm install
```

## Running the Application

### Option 1: Using Startup Scripts

**Windows:**
```batch
cd ui
start_ui.bat
```

**macOS/Linux:**
```bash
cd ui
chmod +x start_ui.sh
./start_ui.sh
```

### Option 2: Manual Startup

**Terminal 1 - Start Backend:**
```bash
# From project root with venv activated
python -m ui.run_backend
```

The API server will start at `http://localhost:8000`

**Terminal 2 - Start Frontend:**
```bash
cd ui/frontend
npm run dev
```

The UI will be available at `http://localhost:5173`

## Usage Guide

### 1. Select Data Source

In the left sidebar:

1. **Source Type**: Choose between:
   - **Local Files**: CSV files in the `data/` directory
   - **Alpaca API**: Live market data (requires API credentials)

2. **File/Ticker**: Select the specific data source:
   - For local: Choose from available CSV files
   - For Alpaca: Select a stock ticker (SPY, AAPL, etc.)

### 2. Configure Date Range (Optional)

- Set **Start Date** and **End Date** to filter the data
- Leave empty to load all available data

### 3. Configure Regime Parameters

Adjust the regime learning parameters:

| Parameter | Description | Range | Default |
|-----------|-------------|-------|---------|
| Number of Clusters | Number of market regimes to identify | 2-10 | 5 |
| Window Size | Temporal window for state representation | 20-120 bars | 60 |
| PCA Components | Dimensionality of latent state space | 2-16 | 8 |

### 4. Load Data

Click **"Load Data"** to:
1. Load OHLCV price data
2. Compute features (returns, volatility, volume, etc.)
3. Learn regime states via PCA + K-Means clustering
4. Calculate statistics

### 5. Explore the Charts Tab

**Price Chart with Regimes:**
- Candlestick chart showing price movement
- Color-coded background regions indicating regime states
- Range slider for zooming into specific periods
- Pan and zoom with mouse/touch

**Volume Chart:**
- Bar chart of trading volume
- Green/red coloring based on price direction

**Regime Distribution:**
- Pie chart showing proportion of time spent in each regime

**Regime Performance:**
- Bar chart of Sharpe ratios by regime
- Green bars = positive Sharpe (favorable regimes)
- Red bars = negative Sharpe (unfavorable regimes)

**Transition Matrix:**
- Heatmap showing probability of transitioning between regimes
- Darker colors = higher probability

### 6. Explore the Features Tab

- Click feature buttons to toggle their display
- Each selected feature shows as a time series chart
- Available features include:
  - **Returns**: r1, r5, r15, r60 (1, 5, 15, 60-minute returns)
  - **Volatility**: rv_60, range_1, range_z_60
  - **Volume**: relvol_60, vol_z_60
  - **Intrabar**: clv (close location value), body_ratio
  - **Anchor**: dist_vwap_60, breakout_20
  - **Time**: tod_sin, tod_cos (time-of-day cyclical)

### 7. View Statistics Tab

**Price Data Summary:**
- Total bars, date range
- Current price, total return
- Price range, daily volatility

**Regime Statistics Table:**
- Sample count per regime
- Mean return and standard deviation
- Sharpe ratio (annualized)
- PCA explained variance

**Feature Statistics Table:**
- Min, max, mean, std, median for each feature

## Display Options

Toggle these in the sidebar:

- **Show Volume**: Display/hide volume chart
- **Show Regime Backgrounds**: Display/hide colored regime overlays

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sources` | GET | List available data sources |
| `/api/ohlcv/{name}` | GET | Get OHLCV price data |
| `/api/features/{name}` | GET | Get computed features |
| `/api/regimes/{name}` | GET | Get regime states and info |
| `/api/statistics/{name}` | GET | Get statistics summary |
| `/api/cache` | DELETE | Clear data cache |
| `/docs` | GET | Interactive API documentation |

### Query Parameters

All data endpoints accept:
- `source_type`: "local" or "alpaca"
- `start_date`: YYYY-MM-DD format (optional)
- `end_date`: YYYY-MM-DD format (optional)

Regime endpoint also accepts:
- `n_clusters`: Number of regimes (2-10)
- `window_size`: Temporal window size (10-200)
- `n_components`: PCA components (2-20)

## Alpaca API Setup

To use Alpaca data, set environment variables:

```bash
# Windows
set ALPACA_API_KEY=your_api_key
set ALPACA_SECRET_KEY=your_secret_key

# macOS/Linux
export ALPACA_API_KEY=your_api_key
export ALPACA_SECRET_KEY=your_secret_key
```

Or create a `.env` file in the project root.

## Local Data Format

CSV files should have columns:
- `timestamp` (or `date`, `datetime`)
- `open`
- `high`
- `low`
- `close`
- `volume`

Supported date formats:
- `YYYY-MM-DD HH:MM:SS`
- `DD/MM/YYYY HH:MM`
- `MM/DD/YYYY HH:MM`

## Troubleshooting

### Backend won't start
```bash
# Check if port 8000 is in use
netstat -an | findstr 8000  # Windows
lsof -i :8000               # macOS/Linux

# Try a different port
python -m uvicorn ui.backend.api:app --port 8001
```

### Frontend can't connect to backend
- Ensure backend is running on port 8000
- Check browser console for CORS errors
- Verify the proxy setting in `vite.config.ts`

### No data sources showing
- Ensure CSV files are in the `data/` directory
- Check that files have `.csv` extension
- Verify file format matches expected OHLCV schema

### Regime computation fails
- Ensure you have enough data points (> window_size)
- Try reducing window_size or n_clusters
- Check that data doesn't have too many missing values

## Development

### Run frontend in development mode
```bash
cd ui/frontend
npm run dev
```

### Build frontend for production
```bash
cd ui/frontend
npm run build
```

### Run backend with auto-reload
```bash
python -m uvicorn ui.backend.api:app --reload
```

## Tech Stack

**Backend:**
- FastAPI - Modern Python web framework
- Uvicorn - ASGI server
- Pandas/NumPy - Data manipulation
- Scikit-learn - PCA and K-Means clustering

**Frontend:**
- React 18 - UI framework
- TypeScript - Type safety
- Vite - Build tool
- Plotly.js - Interactive charts
- Axios - HTTP client
