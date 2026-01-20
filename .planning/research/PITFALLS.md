# Pitfalls Research: Algomatic State

**Domain:** ML-based algorithmic trading with state representation
**Researched:** 2026-01-19
**Confidence:** HIGH (multiple authoritative sources cross-referenced)

## Critical Pitfalls

### Data Pitfalls

#### 1. Look-Ahead Bias / Data Leakage
- **What goes wrong:** Model uses information that wouldn't be available at trade time. Common in minute-bar data where features are computed using the full bar before it closes.
- **Warning signs:**
  - Sharpe ratio > 1.5 in backtest
  - Model performs dramatically better in backtest than paper trading
  - Very smooth equity curve with few drawdowns
- **Prevention:**
  - Use only data available at bar open for predictions
  - Implement strict temporal splits (train only on past data)
  - Consider tick bars or activity-driven bars that complete after predetermined volume
  - Apply all transformations (scaling, encoding) using only training data
- **Phase:** Data Pipeline - implement data access patterns that enforce temporal boundaries
- **Sources:** [IBM - Data Leakage](https://www.ibm.com/think/topics/data-leakage-machine-learning), [MQL5 - Data Leakage and Timestamp Fixes](https://www.mql5.com/en/articles/17520)

#### 2. Survivorship Bias
- **What goes wrong:** Backtesting only includes securities that currently exist, ignoring delisted, bankrupt, or merged companies. This dramatically inflates backtest returns.
- **Warning signs:**
  - Strategy only tested on current S&P 500 constituents
  - No handling of corporate actions (splits, mergers)
  - Backtest universe doesn't match historical reality
- **Prevention:**
  - Include delisted symbols in historical data
  - Use point-in-time universe selection
  - Track rebalances, splits, and corporate actions
- **Phase:** Data Pipeline - ensure data includes historical constituents
- **Sources:** [StarQube - 7 Deadly Sins of Backtesting](https://starqube.com/backtesting-investment-strategies/)

#### 3. Minute Data Gaps and Overnight Handling
- **What goes wrong:** Missing data during low-activity periods or overnight gaps creates false signals or model confusion. Different data providers build candles differently (by trade timestamp vs. block time).
- **Warning signs:**
  - Unexpected trades at market open
  - Features behave erratically during pre/post market
  - Gaps between close and next open not handled
- **Prevention:**
  - Validate timestamps and check for missing minutes
  - Don't forward-fill missing candles without understanding implications
  - Handle overnight gaps explicitly in feature engineering
  - Verify Alpaca data aggregation method matches your assumptions
- **Phase:** Data Pipeline - implement data validation and gap handling
- **Sources:** [CoinAPI - OHLCV Data Explained](https://www.coinapi.io/blog/ohlcv-data-explained-real-time-updates-websocket-behavior-and-trading-applications)

#### 4. Third-Party Data Discrepancies
- **What goes wrong:** Alpaca uses third-party data providers, meaning historical data may not perfectly match prices traded on the platform. This creates backtest-to-live discrepancy.
- **Warning signs:**
  - Fill prices in live trading differ from backtest assumptions
  - Strategy performs differently on different data sources
- **Prevention:**
  - Test data consistency between historical and live feeds
  - Build in tolerance for small price discrepancies
  - Compare multiple data sources during development
- **Phase:** Data Pipeline - add data source validation
- **Sources:** [AlgoTrading101 - Alpaca Trading Review](https://algotrading101.com/learn/alpaca-trading-review/)

---

### ML/State Representation Pitfalls

#### 5. Autoencoder Bottleneck Misconfiguration
- **What goes wrong:** Excessive noise augmentation or too-large bottleneck sizes impair autoencoder performance. Too small loses important patterns; too large doesn't compress enough.
- **Warning signs:**
  - Reconstruction loss plateaus at high value
  - Latent representations don't separate regimes
  - State vectors are highly correlated with raw features (no compression)
- **Prevention:**
  - Systematically test bottleneck sizes (start small, increase if needed)
  - Use balanced noise augmentation
  - Visualize latent space to verify meaningful structure
  - Compare reconstruction quality across different market conditions
- **Phase:** State Representation - hyperparameter tuning with validation
- **Sources:** [Supervised Autoencoder MLP for Financial Time Series](https://journalofbigdata.springeropen.com/articles/10.1186/s40537-025-01267-7)

#### 6. Treating Time Series as Static Data
- **What goes wrong:** Using standard ML approaches (random forests, XGBoost) without proper time series handling. These models assume data points are independently and identically distributed (IID), which is false for time series.
- **Warning signs:**
  - Model trained on shuffled data
  - No lag features or temporal encoding
  - Cross-validation uses random splits instead of temporal splits
- **Prevention:**
  - Always use temporal train/test splits
  - Include lag features explicitly
  - Use time-aware architectures (LSTM, temporal convolutions)
  - Never shuffle time series data
- **Phase:** Feature Engineering and State Representation
- **Sources:** [Feature Engineering for Time-Series Data](https://medium.com/@karanbhutani477/feature-engineering-for-time-series-data-a-deep-yet-intuitive-guide-b544aeb26ec2)

#### 7. PyTorch Training Pitfalls
- **What goes wrong:** Common PyTorch mistakes derail time series model training: forgetting to scale data, not setting device correctly, train/eval mode confusion, batch processing biases.
- **Warning signs:**
  - Loss explodes during training
  - Model predictions are constant regardless of input
  - GPU not being utilized
  - Dropout only occurring once per epoch
- **Prevention:**
  - ALWAYS scale/normalize data (99% of use cases benefit)
  - Set device explicitly (`cuda` vs `cpu`)
  - Call `model.train()` inside training loop, close to inference
  - Use dynamic slicing with random starting indices for batches
  - Plot predictions at each training step, not just loss
- **Phase:** State Representation - model training implementation
- **Sources:** [PyTorch Common Mistakes Guide](https://www.analyticsvidhya.com/blog/2023/02/pytorch-a-comprehensive-guide-to-common-mistakes/), [Training Time Series Models in PyTorch](https://towardsdatascience.com/training-time-series-forecasting-models-in-pytorch-81ef9a66bd3a/)

#### 8. Regime Clustering Without Stability
- **What goes wrong:** Cluster assignments change dramatically with small data changes. No clear standard for what constitutes a "regime." Models trained on one regime fail in another.
- **Warning signs:**
  - Cluster assignments flip frequently
  - Clusters don't have interpretable meanings
  - Regime detection lags market transitions
- **Prevention:**
  - Test cluster stability across different time windows
  - Use methods designed for distribution clustering (e.g., Wasserstein distance)
  - Build regime detection with expected detection lag in mind
  - Verify clusters have distinct, interpretable characteristics
- **Phase:** Regime Clustering - stability testing
- **Sources:** [Imperial College - Market Regime Classification](https://www.imperial.ac.uk/media/imperial-college/faculty-of-natural-sciences/department-of-mathematics/math-finance/McIndoe.pdf), [Clustering Market Regimes with Wasserstein Distance](https://arxiv.org/abs/2110.11848)

---

### Backtesting Pitfalls

#### 9. Walk-Forward Window Selection Bias
- **What goes wrong:** Window sizes fundamentally shape results. Too short misses market cycles; too long incorporates outdated conditions. WFO still lags regime changes.
- **Warning signs:**
  - Performance varies dramatically with window size changes
  - Parameters require frequent re-optimization
  - Strategy fails immediately after optimization period
- **Prevention:**
  - Test multiple window sizes and verify stability
  - Use rolling windows that match your expected regime duration
  - Expect performance degradation at regime transitions
  - Document window selection rationale
- **Phase:** Walk-Forward Validation - systematic window testing
- **Sources:** [Walk-Forward Optimization Guide](https://blog.quantinsti.com/walk-forward-optimization-introduction/), [QuantStrategy - WFO vs Traditional Backtesting](https://quantstrategy.io/blog/walk-forward-optimization-vs-traditional-backtesting-which/)

#### 10. Overfitting to Maximize Sharpe Ratio
- **What goes wrong:** Repeatedly adjusting strategy to optimize historical Sharpe Ratio finds patterns that don't exist. Backtest performance inflated by up to 50% due to optimization bias.
- **Warning signs:**
  - Sharpe ratio > 3.0 in backtest (very suspicious)
  - Strategy has many optimized parameters
  - Performance degrades significantly in out-of-sample
- **Prevention:**
  - Use out-of-sample testing rigorously
  - Limit number of free parameters
  - Apply Bailey and Lopez de Prado's "deflated Sharpe ratio"
  - Target Sharpe ratio 1.0-2.0 as realistic goal
- **Phase:** Backtesting - implement proper validation methodology
- **Sources:** [QuantStart - Sharpe Ratio for Algorithmic Trading](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/)

#### 11. Sharpe Ratio Calculation Errors
- **What goes wrong:** Wrong annualization factor (using 365 instead of 252 trading days), not including transaction costs, assuming normal distribution of returns.
- **Warning signs:**
  - Sharpe differs significantly from industry benchmarks
  - Net returns not used in calculation
  - Annualization doesn't match trading frequency
- **Prevention:**
  - Use N=252 for daily, N=252*6.5=1638 for hourly
  - Calculate Sharpe AFTER transaction costs
  - Complement with other metrics (Sortino, Calmar, max drawdown)
- **Phase:** Backtesting - implement correct performance metrics
- **Sources:** [QuantStart - Sharpe Ratio](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/)

#### 12. Ignoring Transaction Costs and Slippage
- **What goes wrong:** Backtest assumes perfect fills at mid-price. Real trading faces spreads, slippage, and fees that can reduce returns by 50% or more.
- **Warning signs:**
  - Backtest doesn't model bid-ask spread
  - High-frequency strategies with many trades
  - No slippage model
- **Prevention:**
  - Add realistic transaction costs (Alpaca commission-free, but spreads exist)
  - Model slippage as function of volatility and order size
  - Use conservative slippage estimates (slippage correlates with best trades)
- **Phase:** Backtesting - implement realistic cost models
- **Sources:** [TradersPost - Paper Trading vs Live Trading](https://blog.traderspost.io/article/paper-trading-vs-live-trading-key-differences-and-what-to-expect)

---

### Execution Pitfalls

#### 13. Paper-to-Live Transition Shock
- **What goes wrong:** Paper trading executes at perfect prices; live trading faces slippage, delays, partial fills, and order rejections. Strategy performs dramatically worse live.
- **Warning signs:**
  - No gradual transition plan
  - Full position sizes on day 1
  - No comparison of paper vs. live fill quality
- **Prevention:**
  - Start with minimal capital in live trading
  - Compare fill prices between paper and live
  - Track slippage metrics from day 1
  - Plan 2-4 week transition period with small positions
- **Phase:** Live Trading - implement gradual rollout
- **Sources:** [Alpaca - Paper Trading vs Live Trading Guide](https://alpaca.markets/learn/paper-trading-vs-live-trading-a-data-backed-guide-on-when-to-start-trading-real-money)

#### 14. Alpaca API-Specific Issues
- **What goes wrong:** Conditional orders fail near market close. Rate limits (200 req/min) hit during high activity. Settlement timing (T+1) affects cash availability.
- **Warning signs:**
  - Orders failing without clear error handling
  - Loops sending multiple unintended orders
  - Cash balance discrepancies
- **Prevention:**
  - Implement robust error handling for API calls
  - Add rate limiting in code
  - Monitor conditional orders for reasonability
  - Understand T+1 settlement impacts on position sizing
  - NEVER use loops without safeguards for order submission
- **Phase:** Execution Layer - defensive API integration
- **Sources:** [Alpaca Broker API FAQs](https://docs.alpaca.markets/docs/broker-api-faq)

#### 15. No Kill Switch
- **What goes wrong:** Runaway algorithm continues trading during malfunction. Knight Capital lost $440 million in 45 minutes due to no kill switch.
- **Warning signs:**
  - No daily loss limit
  - No maximum position size enforcement
  - No way to halt trading remotely
- **Prevention:**
  - Implement automatic trading halt on max daily loss
  - Set position limits that cannot be exceeded
  - Build remote kill switch capability
  - Real-time monitoring with alerts
- **Phase:** Risk Management and Live Trading
- **Sources:** [LuxAlgo - Lessons from Algo Trading Failures](https://www.luxalgo.com/blog/lessons-from-algo-trading-failures/)

---

### Risk Management Pitfalls

#### 16. Momentum Crash Exposure
- **What goes wrong:** Momentum strategies suffer severe losses (up to 90% in a month historically) during market reversals. Strategy doesn't adapt to regime change.
- **Warning signs:**
  - No regime-based position adjustment
  - High exposure during market stress
  - Ignoring market drawdown signals
- **Prevention:**
  - Implement regime detection to reduce/halt trading in adverse regimes
  - Consider contrarian positioning 1-3 months after major market loss
  - Use changepoint detection to identify regime shifts faster
  - Reduce position sizes during high volatility
- **Phase:** Regime Clustering and Risk Management
- **Sources:** [Morningstar - Momentum Turning Points](https://www.morningstar.com/markets/achilles-heel-momentum-strategies), [PM Research - Slow Momentum with Fast Reversion](https://www.pm-research.com/content/iijjfds/4/1/111)

#### 17. Improper Position Sizing
- **What goes wrong:** Fixed position sizes don't adapt to volatility or drawdown. Kelly Criterion over-allocates when win probability estimates are wrong.
- **Warning signs:**
  - Same position size regardless of volatility
  - No drawdown-based adjustment
  - Position size > 3% of capital per trade
- **Prevention:**
  - Limit each position to 1-3% of capital
  - Scale position size by inverse volatility
  - Reduce positions during drawdowns automatically
  - Set aside 1.5-2x historical max drawdown as reserve
- **Phase:** Risk Management - position sizing system
- **Sources:** [AlgoTest - Why Max Drawdown Matters](https://algotest.in/blog/why-max-drawdown-matters-in-risk-management/), [Tradetron - Reducing Drawdown](https://tradetron.tech/blog/reducing-drawdown-7-risk-management-techniques-for-algo-traders)

#### 18. Ignoring Max Drawdown in Favor of Returns
- **What goes wrong:** Optimizing for returns without drawdown constraints leads to strategies that blow up. A 50% drawdown requires 100% gain to recover.
- **Warning signs:**
  - No maximum drawdown constraint in optimization
  - Historical max drawdown > 20% acceptable
  - No stress testing against historical crashes
- **Prevention:**
  - Set hard max drawdown limit (15% per project goals)
  - Include drawdown in optimization objective
  - Run Monte Carlo simulations for tail scenarios
  - Stress test against 2008, 2020, 2022 market conditions
- **Phase:** Backtesting and Risk Management
- **Sources:** [Maximum Drawdown Position Sizing](https://www.quantifiedstrategies.com/maximum-drawdown-position-sizing/)

---

## Moderate Pitfalls

### 19. Feature Engineering Without Domain Knowledge
- **What goes wrong:** Features that look predictive are actually noise or spurious correlations.
- **Prevention:** Involve domain expertise; each feature should have economic rationale.
- **Phase:** Feature Engineering

### 20. Cyclical Feature Encoding Errors
- **What goes wrong:** Encoding time features as integers (Monday=0, Sunday=6) treats them as linear when they're cyclical.
- **Prevention:** Use sin/cos encoding for cyclical features (hour, day of week, month).
- **Phase:** Feature Engineering

### 21. Single Timeframe Myopia
- **What goes wrong:** Using only 1-minute data misses larger market structure. Strategy whipsaws on noise.
- **Prevention:** Include multi-timeframe features (5-min, 15-min, hourly context).
- **Phase:** Feature Engineering

### 22. Model Latency in Production
- **What goes wrong:** Complex models (deep transformers) take too long for real-time trading decisions.
- **Prevention:** Test inference latency; simpler models often outperform in practice.
- **Phase:** Live Trading

### 23. Overcomplicating the Strategy
- **What goes wrong:** Adding more indicators and filters to improve backtest performance. Simple momentum strategies often outperform complex ones.
- **Prevention:** Prefer simplicity; complexity should be justified by out-of-sample improvement.
- **Phase:** All phases - maintain simplicity discipline

---

## Minor Pitfalls

### 24. Poor Experiment Tracking
- **What goes wrong:** Can't reproduce good results because parameters weren't logged.
- **Prevention:** Log all hyperparameters, data versions, and random seeds.
- **Phase:** All phases

### 25. Not Handling Corporate Actions
- **What goes wrong:** Stock splits cause apparent price drops; strategy sells based on false signal.
- **Prevention:** Use adjusted prices; validate data around known split dates.
- **Phase:** Data Pipeline

### 26. Timezone Confusion
- **What goes wrong:** Data in UTC, trading in ET, features computed incorrectly.
- **Prevention:** Standardize on one timezone throughout pipeline.
- **Phase:** Data Pipeline

---

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|---------------|------------|
| Data Pipeline | Look-ahead bias in feature computation | Enforce strict temporal boundaries |
| Data Pipeline | Minute data gaps | Implement validation and gap handling |
| Feature Engineering | Data leakage through improper scaling | Scale using only training data |
| Feature Engineering | Cyclical encoding errors | Use sin/cos transforms |
| State Representation | Autoencoder bottleneck misconfiguration | Systematic hyperparameter search |
| State Representation | PyTorch training mode confusion | train() call inside loop |
| Regime Clustering | Unstable cluster assignments | Stability testing across windows |
| Backtesting | Overfitting to Sharpe Ratio | Out-of-sample validation, parameter limits |
| Walk-Forward | Window selection bias | Test multiple window sizes |
| Paper Trading | False confidence from perfect fills | Add slippage/cost models |
| Live Trading | No kill switch | Implement from day 1 |
| Live Trading | Momentum crash exposure | Regime-based position reduction |

---

## Common Mistakes in Similar Projects

### Lessons from Failed ML Trading Projects

1. **Pattern Overfitting**
   - Multiple ML-driven funds launched with impressive backtests, failed in live trading
   - Models learned to exploit peculiarities in historical data (microstructure noise, stale prices)
   - These artifacts don't exist in real-time trading

2. **Governance Failures**
   - Knight Capital: No adequate controls on code deployment
   - No distinction between intended and aberrant behavior in monitoring
   - Risk management blind to operational risks

3. **Flash Crash Lessons**
   - Algorithms designed without market impact consideration
   - No circuit breakers for extreme conditions
   - "Hot potato" effects between algorithmic traders

4. **Complexity Hubris**
   - LTCM: Mathematical models couldn't anticipate true discontinuities
   - Models reflect the past; they can't predict black swans
   - Domain knowledge often outweighs algorithmic complexity

### Red Flags That Predict Failure

1. **Backtest too good to be true** - Sharpe > 3.0, no drawdowns
2. **No out-of-sample validation** - Only in-sample results shown
3. **Many tuned parameters** - More than 5-10 free parameters
4. **No stress testing** - Never tested against 2008, 2020 scenarios
5. **Perfect fills assumed** - No slippage or cost modeling
6. **No kill switch** - No automatic halt mechanism
7. **Single regime training** - Only bull market or low-vol data

---

## Sources

- [IBM - Data Leakage in Machine Learning](https://www.ibm.com/think/topics/data-leakage-machine-learning)
- [MQL5 - Data Leakage and Timestamp Fixes](https://www.mql5.com/en/articles/17520)
- [StarQube - 7 Deadly Sins of Backtesting](https://starqube.com/backtesting-investment-strategies/)
- [QuantStart - Sharpe Ratio for Algorithmic Trading](https://www.quantstart.com/articles/Sharpe-Ratio-for-Algorithmic-Trading-Performance-Measurement/)
- [Walk-Forward Optimization Guide](https://blog.quantinsti.com/walk-forward-optimization-introduction/)
- [Alpaca - Paper Trading vs Live Trading](https://alpaca.markets/learn/paper-trading-vs-live-trading-a-data-backed-guide-on-when-to-start-trading-real-money)
- [Morningstar - Momentum Turning Points](https://www.morningstar.com/markets/achilles-heel-momentum-strategies)
- [PM Research - Slow Momentum with Fast Reversion](https://www.pm-research.com/content/iijjfds/4/1/111)
- [LuxAlgo - Lessons from Algo Trading Failures](https://www.luxalgo.com/blog/lessons-from-algo-trading-failures/)
- [AlgoTest - Why Max Drawdown Matters](https://algotest.in/blog/why-max-drawdown-matters-in-risk-management/)
- [Supervised Autoencoder MLP for Financial Time Series](https://journalofbigdata.springeropen.com/articles/10.1186/s40537-025-01267-7)
- [Imperial College - Market Regime Classification](https://www.imperial.ac.uk/media/imperial-college/faculty-of-natural-sciences/department-of-mathematics/math-finance/McIndoe.pdf)
- [PyTorch Common Mistakes Guide](https://www.analyticsvidhya.com/blog/2023/02/pytorch-a-comprehensive-guide-to-common-mistakes/)
- [Alpaca Broker API FAQs](https://docs.alpaca.markets/docs/broker-api-faq)
- [PMC - Systemic Failures in Algorithmic Trading](https://pmc.ncbi.nlm.nih.gov/articles/PMC8978471/)
