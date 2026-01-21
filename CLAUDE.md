# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Algorithmic trading project using the Alpaca API for market data and order execution.

## Development Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

## Dependencies

- `alpaca-py`: Alpaca Markets SDK for trading and market data

## Data

The `data/` directory contains market data CSV files (not tracked in git).
