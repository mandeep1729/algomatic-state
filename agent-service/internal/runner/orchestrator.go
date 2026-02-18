package runner

import (
	"context"
	"log/slog"
	"sync"
	"time"

	"github.com/algomatic/agent-service/internal/alpaca"
	"github.com/algomatic/agent-service/internal/repository"
	resolverPkg "github.com/algomatic/agent-service/internal/strategy"
	"github.com/algomatic/strats100/go-strats/pkg/backend"
)

// runnerEntry tracks a running agent goroutine.
type runnerEntry struct {
	cancel context.CancelFunc
}

// Orchestrator manages the lifecycle of agent runner goroutines.
// It polls the database for active agents and starts/stops runners accordingly.
type Orchestrator struct {
	agentRepo     *repository.AgentRepo
	orderRepo     *repository.OrderRepo
	activityRepo  *repository.ActivityRepo
	resolver      *resolverPkg.Resolver
	alpacaClient  *alpaca.TradingClient
	backendClient *backend.Client
	pollInterval  time.Duration
	maxErrors     int
	logger        *slog.Logger

	mu      sync.Mutex
	runners map[int]*runnerEntry
	wg      sync.WaitGroup
}

// NewOrchestrator creates a new Orchestrator.
func NewOrchestrator(
	agentRepo *repository.AgentRepo,
	orderRepo *repository.OrderRepo,
	activityRepo *repository.ActivityRepo,
	resolver *resolverPkg.Resolver,
	alpacaClient *alpaca.TradingClient,
	backendClient *backend.Client,
	pollInterval time.Duration,
	maxErrors int,
	logger *slog.Logger,
) *Orchestrator {
	return &Orchestrator{
		agentRepo:     agentRepo,
		orderRepo:     orderRepo,
		activityRepo:  activityRepo,
		resolver:      resolver,
		alpacaClient:  alpacaClient,
		backendClient: backendClient,
		pollInterval:  pollInterval,
		maxErrors:     maxErrors,
		logger:        logger,
		runners:       make(map[int]*runnerEntry),
	}
}

// Run starts the reconcile loop. Blocks until ctx is cancelled.
func (o *Orchestrator) Run(ctx context.Context) {
	o.logger.Info("Orchestrator started", "poll_interval", o.pollInterval)

	ticker := time.NewTicker(o.pollInterval)
	defer ticker.Stop()

	// Reconcile immediately on start
	o.reconcile(ctx)

	for {
		select {
		case <-ctx.Done():
			o.logger.Info("Orchestrator shutting down, stopping all runners...")
			o.stopAll()
			o.wg.Wait()
			o.logger.Info("All runners stopped")
			return
		case <-ticker.C:
			o.reconcile(ctx)
		}
	}
}

// reconcile syncs the in-memory runner map with the database.
func (o *Orchestrator) reconcile(ctx context.Context) {
	agents, err := o.agentRepo.GetActiveAgents(ctx)
	if err != nil {
		o.logger.Error("Failed to query active agents", "error", err)
		return
	}

	o.mu.Lock()
	defer o.mu.Unlock()

	// Build set of active agent IDs
	activeIDs := make(map[int]bool, len(agents))
	for _, a := range agents {
		activeIDs[a.ID] = true
	}

	// Stop runners for agents that are no longer active
	for id, entry := range o.runners {
		if !activeIDs[id] {
			o.logger.Info("Stopping runner for deactivated agent", "agent_id", id)
			entry.cancel()
			delete(o.runners, id)
		}
	}

	// Start runners for new active agents
	for _, a := range agents {
		if _, running := o.runners[a.ID]; running {
			continue
		}

		o.logger.Info("Starting runner for agent",
			"agent_id", a.ID, "name", a.Name, "symbol", a.Symbol,
		)

		runCtx, cancel := context.WithCancel(ctx)
		o.runners[a.ID] = &runnerEntry{cancel: cancel}

		loop := &agentLoop{
			agent:         a,
			agentRepo:     o.agentRepo,
			orderRepo:     o.orderRepo,
			activityRepo:  o.activityRepo,
			resolver:      o.resolver,
			alpacaClient:  o.alpacaClient,
			backendClient: o.backendClient,
			maxErrors:     o.maxErrors,
			logger:        o.logger.With("agent_id", a.ID, "symbol", a.Symbol),
		}

		o.wg.Add(1)
		go func(agentID int) {
			defer o.wg.Done()
			loop.run(runCtx)
			o.logger.Info("Runner exited", "agent_id", agentID)
		}(a.ID)
	}

	o.logger.Debug("Reconcile complete", "active_agents", len(agents), "running", len(o.runners))
}

// stopAll cancels all running agent goroutines.
func (o *Orchestrator) stopAll() {
	o.mu.Lock()
	defer o.mu.Unlock()

	for id, entry := range o.runners {
		entry.cancel()
		delete(o.runners, id)
	}
}
