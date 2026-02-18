module github.com/algomatic/agent-service

go 1.24.0

require (
	github.com/algomatic/strats100/go-strats v0.0.0
	github.com/jackc/pgx/v5 v5.8.0
)

replace github.com/algomatic/strats100/go-strats => ../go-strats

require (
	github.com/jackc/pgpassfile v1.0.0 // indirect
	github.com/jackc/pgservicefile v0.0.0-20240606120523-5a60cdf6a761 // indirect
	github.com/jackc/puddle/v2 v2.2.2 // indirect
	golang.org/x/sync v0.19.0 // indirect
	golang.org/x/text v0.32.0 // indirect
)
