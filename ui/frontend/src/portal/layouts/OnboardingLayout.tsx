import { Outlet } from 'react-router-dom';

export default function OnboardingLayout() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <div className="w-full max-w-lg px-6">
        <h1 className="mb-8 text-center text-2xl font-semibold">Trading Buddy Setup</h1>
        <Outlet />
      </div>
    </div>
  );
}
