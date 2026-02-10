# Trading Buddy UI (React + Vite)

This is a UI scaffold for the evaluation-first **Position Campaigns** experience:

- Campaign list: `/app/trades`
- Campaign detail with multi-leg timeline + decision tabs: `/app/trade/:id`
- Proposed trade evaluation: `/app/evaluate`
- Broker integrations settings: `/app/settings/brokers`

## Run

```bash
npm install
npm run dev
```

## Notes

- Data is mocked under `src/data/mock.ts`.
- The Context panel autosaves to in-memory state; replace `onAutosave` with API calls later.
