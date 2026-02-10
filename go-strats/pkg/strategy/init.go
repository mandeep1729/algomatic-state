package strategy

import "github.com/algomatic/strats100/go-strats/pkg/types"

// init registers all 100 strategies on package load.
func init() {
	all := make([]*types.StrategyDef, 0, 100)
	all = append(all, trendStrategies()...)
	all = append(all, meanReversionStrategies()...)
	all = append(all, breakoutStrategies()...)
	all = append(all, volumeFlowStrategies()...)
	all = append(all, patternStrategies()...)
	all = append(all, regimeStrategies()...)
	RegisterAll(all)
}
