package runner

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"math"
	"strconv"
	"time"

	"github.com/algomatic/agent-service/internal/alpaca"
	"github.com/algomatic/agent-service/internal/repository"
	resolverPkg "github.com/algomatic/agent-service/internal/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/backend"
	"github.com/algomatic/strats100/go-strats/pkg/types"
)

// agentLoop runs the trading loop for a single agent.
type agentLoop struct {
	agent        repository.TradingAgentRow
	agentRepo    *repository.AgentRepo
	orderRepo    *repository.OrderRepo
	activityRepo *repository.ActivityRepo
	resolver     *resolverPkg.Resolver
	alpacaClient *alpaca.TradingClient
	backendClient *backend.Client
	maxErrors    int
	logger       *slog.Logger
}

// run executes the agent's trading loop at the configured interval.
// It blocks until the context is cancelled.
func (l *agentLoop) run(ctx context.Context) {
	agentID := l.agent.ID
	interval := time.Duration(l.agent.IntervalMinutes) * time.Minute

	l.logger.Info("Agent loop started",
		"agent_id", agentID, "symbol", l.agent.Symbol,
		"interval", interval, "timeframe", l.agent.Timeframe,
	)

	l.logActivity(ctx, "loop_started",
		fmt.Sprintf("Agent loop started for %s (%s)", l.agent.Symbol, l.agent.Timeframe),
		"info",
	)

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	// Run immediately on start, then on ticker
	l.tick(ctx)

	for {
		select {
		case <-ctx.Done():
			l.logger.Info("Agent loop stopping", "agent_id", agentID)
			return
		case <-ticker.C:
			l.tick(ctx)
		}
	}
}

// tick performs one iteration of the trading loop.
func (l *agentLoop) tick(ctx context.Context) {
	agentID := l.agent.ID

	// 1. Check if market is open
	clock, err := l.alpacaClient.GetClock(ctx)
	if err != nil {
		l.handleError(ctx, fmt.Errorf("checking market clock: %w", err))
		return
	}
	if !clock.IsOpen {
		l.logger.Debug("Market closed, skipping tick", "agent_id", agentID, "next_open", clock.NextOpen)
		return
	}

	// 2. Resolve strategy
	stratDef, err := l.resolver.Resolve(ctx, l.agent.StrategyID)
	if err != nil {
		l.handleError(ctx, fmt.Errorf("resolving strategy: %w", err))
		return
	}

	// 3. Fetch bar data
	end := time.Now().UTC()
	start := end.AddDate(0, 0, -l.agent.LookbackDays)

	barData, err := l.backendClient.GetBarData(ctx, l.agent.Symbol, l.agent.Timeframe, start, end)
	if err != nil {
		l.handleError(ctx, fmt.Errorf("fetching bar data: %w", err))
		return
	}

	if len(barData) < 2 {
		l.logger.Debug("Not enough bar data", "agent_id", agentID, "bars", len(barData))
		return
	}

	// 4. Load current position from DB
	var position *PositionState
	if len(l.agent.CurrentPosition) > 0 {
		var ps PositionState
		if err := json.Unmarshal(l.agent.CurrentPosition, &ps); err == nil && ps.Qty > 0 {
			position = &ps
		}
	}

	// 5. Evaluate signal
	signal := evaluateSignal(barData, stratDef, position, l.logger)
	signalName := "none"
	if signal != nil {
		signalName = signal.Action
	}

	// 6. Execute signal
	if signal != nil {
		if err := l.executeSignal(ctx, signal, barData, stratDef, position); err != nil {
			l.handleError(ctx, fmt.Errorf("executing signal %s: %w", signal.Action, err))
			return
		}
	}

	// 7. Update last run
	if err := l.agentRepo.UpdateLastRun(ctx, agentID, time.Now(), signalName); err != nil {
		l.logger.Error("Failed to update last run", "agent_id", agentID, "error", err)
	}

	l.logger.Debug("Tick complete",
		"agent_id", agentID, "signal", signalName, "bars", len(barData),
	)
}

// executeSignal places orders based on the signal.
func (l *agentLoop) executeSignal(
	ctx context.Context,
	signal *Signal,
	barData []types.BarData,
	stratDef *types.StrategyDef,
	position *PositionState,
) error {
	agentID := l.agent.ID

	switch signal.Action {
	case "entry_long", "entry_short":
		return l.executeEntry(ctx, signal, barData, stratDef)

	case "exit_long", "exit_short":
		if position == nil {
			l.logger.Warn("Exit signal but no position", "agent_id", agentID)
			return nil
		}
		return l.executeExit(ctx, signal)

	default:
		return fmt.Errorf("unknown signal action: %s", signal.Action)
	}
}

// executeEntry places a bracket order for entry.
func (l *agentLoop) executeEntry(
	ctx context.Context,
	signal *Signal,
	barData []types.BarData,
	stratDef *types.StrategyDef,
) error {
	agentID := l.agent.ID
	lastBar := barData[len(barData)-1]
	price := lastBar.Bar.Close

	// Calculate quantity from position size
	qty := int(l.agent.PositionSizeDollars / price)
	if qty < 1 {
		l.logger.Warn("Position size too small for one share",
			"agent_id", agentID, "price", price, "size_dollars", l.agent.PositionSizeDollars,
		)
		return nil
	}

	side := "buy"
	if signal.Direction == types.Short {
		side = "sell"
	}

	// Build bracket order with ATR-based stop/target
	clientOrderID := fmt.Sprintf("agent-%d-%d", agentID, time.Now().UnixMilli())
	orderReq := &alpaca.OrderRequest{
		Symbol:        l.agent.Symbol,
		Qty:           strconv.Itoa(qty),
		Side:          side,
		Type:          "market",
		TimeInForce:   "day",
		ClientOrderID: clientOrderID,
	}

	// Add bracket if we have ATR-based exits
	atrVal, hasATR := lastBar.Indicators.Get("atr_14")
	if hasATR && (stratDef.HasATRStop() || stratDef.HasATRTarget()) {
		orderReq.OrderClass = "bracket"

		if stratDef.HasATRTarget() {
			var targetPrice float64
			if signal.Direction == types.Long {
				targetPrice = price + stratDef.ATRTargetMult*atrVal
			} else {
				targetPrice = price - stratDef.ATRTargetMult*atrVal
			}
			orderReq.TakeProfit = &alpaca.TakeProfit{
				LimitPrice: formatPrice(targetPrice),
			}
		}

		if stratDef.HasATRStop() {
			var stopPrice float64
			if signal.Direction == types.Long {
				stopPrice = price - stratDef.ATRStopMult*atrVal
			} else {
				stopPrice = price + stratDef.ATRStopMult*atrVal
			}
			orderReq.StopLoss = &alpaca.StopLoss{
				StopPrice: formatPrice(stopPrice),
			}
		}
	}

	// Submit to Alpaca
	resp, err := l.alpacaClient.SubmitOrder(ctx, orderReq)
	if err != nil {
		return fmt.Errorf("submitting order: %w", err)
	}

	// Persist order
	now := time.Now()
	signalMeta, _ := json.Marshal(map[string]interface{}{
		"signal":    signal.Action,
		"price":     price,
		"atr":       atrVal,
		"bars_used": len(barData),
	})

	_, err = l.orderRepo.CreateOrder(ctx, &repository.AgentOrderRow{
		AgentID:        agentID,
		AccountID:      l.agent.AccountID,
		Symbol:         l.agent.Symbol,
		Side:           side,
		Quantity:        float64(qty),
		OrderType:      "market",
		ClientOrderID:  clientOrderID,
		BrokerOrderID:  &resp.ID,
		Status:         resp.Status,
		SignalDirection: &signal.Action,
		SignalMetadata:  signalMeta,
		SubmittedAt:    &now,
	})
	if err != nil {
		l.logger.Error("Failed to persist order", "agent_id", agentID, "error", err)
	}

	// Update position state
	posState := PositionState{
		Direction:  signal.Direction,
		Qty:        float64(qty),
		EntryPrice: price,
		EntryTime:  now.Format(time.RFC3339),
		OrderID:    resp.ID,
	}
	posJSON, _ := json.Marshal(posState)
	if err := l.agentRepo.UpdateCurrentPosition(ctx, agentID, posJSON); err != nil {
		l.logger.Error("Failed to update position", "agent_id", agentID, "error", err)
	}

	l.logActivity(ctx, "order_submitted",
		fmt.Sprintf("Submitted %s order: %d shares of %s @ ~%.2f", side, qty, l.agent.Symbol, price),
		"info",
	)

	return nil
}

// executeExit closes the current position.
func (l *agentLoop) executeExit(ctx context.Context, signal *Signal) error {
	agentID := l.agent.ID

	if err := l.alpacaClient.ClosePosition(ctx, l.agent.Symbol); err != nil {
		return fmt.Errorf("closing position: %w", err)
	}

	// Clear position state
	if err := l.agentRepo.UpdateCurrentPosition(ctx, agentID, nil); err != nil {
		l.logger.Error("Failed to clear position", "agent_id", agentID, "error", err)
	}

	l.logActivity(ctx, "position_closed",
		fmt.Sprintf("Closed position for %s (signal: %s)", l.agent.Symbol, signal.Action),
		"info",
	)

	return nil
}

// handleError increments error count and potentially sets status to error.
func (l *agentLoop) handleError(ctx context.Context, err error) {
	agentID := l.agent.ID
	l.logger.Error("Agent error", "agent_id", agentID, "error", err)

	count, incErr := l.agentRepo.IncrementErrors(ctx, agentID, err.Error())
	if incErr != nil {
		l.logger.Error("Failed to increment errors", "agent_id", agentID, "error", incErr)
		return
	}

	l.logActivity(ctx, "error",
		fmt.Sprintf("Error (%d/%d): %s", count, l.maxErrors, err.Error()),
		"error",
	)

	if count >= l.maxErrors {
		l.logger.Error("Max consecutive errors reached, setting agent to error state",
			"agent_id", agentID, "errors", count,
		)
		if setErr := l.agentRepo.SetStatus(ctx, agentID, "error"); setErr != nil {
			l.logger.Error("Failed to set error status", "agent_id", agentID, "error", setErr)
		}
		l.logActivity(ctx, "status_change",
			fmt.Sprintf("Agent stopped: %d consecutive errors", count),
			"error",
		)
	}
}

// logActivity is a convenience wrapper for activity logging.
func (l *agentLoop) logActivity(ctx context.Context, actType, message, severity string) {
	if err := l.activityRepo.Log(
		ctx, l.agent.ID, l.agent.AccountID, actType, message, nil, severity,
	); err != nil {
		l.logger.Error("Failed to log activity", "agent_id", l.agent.ID, "error", err)
	}
}

// formatPrice formats a price to 2 decimal places for Alpaca.
func formatPrice(price float64) string {
	rounded := math.Round(price*100) / 100
	return strconv.FormatFloat(rounded, 'f', 2, 64)
}
