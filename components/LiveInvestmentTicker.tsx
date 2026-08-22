import React, { useEffect, useRef, useState } from "react";

type PlanKey = "starter" | "elite" | "gold" | "platinum" | "shareholder";

type Props = {
  planType: PlanKey;
  principalAmount: number; // USD
  startTimestamp: string | number | Date; // ISO string, ms epoch, or Date
  onComplete?: () => void;
  currency?: string; // default "USD"
  smoothMs?: number; // smoothing window in ms (controls lerp speed)
};

const SECONDS_PER_DAY = 86400;
const SECONDS_PER_YEAR = 365 * SECONDS_PER_DAY;

const PLAN_DEFS: Record<
  PlanKey,
  {
    displayName: string;
    dailyRate?: number;
    totalEarningsFactor?: number;
    durationSeconds: number;
    min: number;
    max: number;
  }
> = {
  starter: {
    displayName: "Starter Plan",
    dailyRate: 0.025,
    durationSeconds: 7 * SECONDS_PER_DAY,
    min: 100,
    max: 1_999,
  },
  elite: {
    displayName: "Elite Plan",
    dailyRate: 0.03,
    durationSeconds: 7 * SECONDS_PER_DAY,
    min: 2_000,
    max: 9_999,
  },
  gold: {
    displayName: "Gold Plan",
    dailyRate: 0.04,
    durationSeconds: 7 * SECONDS_PER_DAY,
    min: 10_000,
    max: 49_999,
  },
  platinum: {
    displayName: "Platinum Plan",
    dailyRate: 0.05,
    durationSeconds: 7 * SECONDS_PER_DAY,
    min: 50_000,
    max: 499_999,
  },
  shareholder: {
    displayName: "Shareholder Plan",
    totalEarningsFactor: 1.2,
    durationSeconds: SECONDS_PER_YEAR,
    min: 15_000,
    max: 1_000_000,
  },
};

function parseStartTimestamp(input: string | number | Date): number {
  if (input instanceof Date) return Math.floor(input.getTime() / 1000);
  if (typeof input === "number") {
    if (input > 1e12) return Math.floor(input / 1000);
    return Math.floor(input);
  }
  const parsed = Date.parse(String(input));
  if (isNaN(parsed)) throw new Error("Invalid startTimestamp");
  return Math.floor(parsed / 1000);
}

export default function LiveInvestmentTicker({
  planType,
  principalAmount,
  startTimestamp,
  onComplete,
  currency = "USD",
  smoothMs = 200,
}: Props) {
  const def = PLAN_DEFS[planType];
  if (!def) throw new Error("Unknown planType");

  const startSecRef = useRef<number>(parseStartTimestamp(startTimestamp));
  const [nowSec, setNowSec] = useState<number>(Math.floor(Date.now() / 1000));
  const rafRef = useRef<number | null>(null);
  const targetEarningsRef = useRef<number>(0);
  const targetBalanceRef = useRef<number>(principalAmount);
  const displayedEarningsRef = useRef<number>(0);
  const displayedBalanceRef = useRef<number>(principalAmount);
  const [, tick] = useState(0);

  const fmt = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
    minimumFractionDigits: 2,
  });

  function computeTargets(currentUnixSec: number) {
    const elapsed = Math.max(0, currentUnixSec - startSecRef.current);
    const cappedElapsed = Math.min(elapsed, def.durationSeconds);

    let earnings = 0;
    let maxEarnings = 0;

    if (planType === "shareholder") {
      const factor = def.totalEarningsFactor ?? 0;
      maxEarnings = principalAmount * factor;
      const perSecond = maxEarnings / def.durationSeconds;
      earnings = perSecond * cappedElapsed;
    } else {
      const daily = def.dailyRate ?? 0;
      maxEarnings = principalAmount * daily * (def.durationSeconds / SECONDS_PER_DAY);
      const perSecondRate = daily / SECONDS_PER_DAY;
      earnings = principalAmount * perSecondRate * cappedElapsed;
    }

    if (earnings >= maxEarnings) {
      earnings = maxEarnings;
      if (onComplete) setTimeout(() => onComplete(), 0);
    }

    targetEarningsRef.current = earnings;
    targetBalanceRef.current = principalAmount + earnings;
    return {
      earnings,
      balance: principalAmount + earnings,
      elapsed: cappedElapsed,
      progress: Math.min(1, cappedElapsed / def.durationSeconds),
      remainingSeconds: Math.max(0, def.durationSeconds - cappedElapsed),
      maxEarnings,
    };
  }

  function lerp(a: number, b: number, t: number) {
    return a + (b - a) * t;
  }

  useEffect(() => {
    let lastTime = performance.now();

    function frame(nowMs: number) {
      const nowUnix = Math.floor(Date.now() / 1000);
      setNowSec(nowUnix);

      computeTargets(nowUnix);

      const dt = Math.max(1, nowMs - lastTime);
      lastTime = nowMs;
      const t = Math.min(1, dt / smoothMs);

      displayedEarningsRef.current = lerp(displayedEarningsRef.current, targetEarningsRef.current, t);
      displayedBalanceRef.current = lerp(displayedBalanceRef.current, targetBalanceRef.current, t);

      tick((s) => s + 1);

      rafRef.current = requestAnimationFrame(frame);
    }

    rafRef.current = requestAnimationFrame(frame);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [planType, principalAmount, startTimestamp, smoothMs]);

  const precise = computeTargets(nowSec);
  const displayedEarnings = displayedEarningsRef.current;
  const displayedBalance = displayedBalanceRef.current;

  function formatSeconds(sec: number) {
    const d = Math.floor(sec / SECONDS_PER_DAY);
    const h = Math.floor((sec % SECONDS_PER_DAY) / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = Math.floor(sec % 60);
    if (d > 0) return `${d}d ${h}h`;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  const outOfRange =
    principalAmount < def.min || principalAmount > def.max
      ? `Investment amount outside plan limits: min ${fmt.format(def.min)}, max ${fmt.format(def.max)}`
      : null;

  return (
    <div className="w-full max-w-3xl mx-auto bg-gradient-to-b from-[#070709]/60 via-transparent to-transparent rounded-2xl p-6 shadow-xl border border-white/6">
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          <div className="text-sm uppercase text-neutral-300 tracking-wider">{def.displayName}</div>
          <div className="mt-3">
            <div className="text-3xl md:text-4xl font-semibold text-white leading-tight">
              <span className="mr-2">{fmt.format(displayedBalance)}</span>
            </div>
            <div className="mt-2 text-sm text-neutral-300">Current Investment Balance</div>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-4">
            <div>
              <div className="text-xl font-medium text-[#C9A24B]">{fmt.format(displayedEarnings)}</div>
              <div className="text-sm text-neutral-400">Total Earnings Accumulating</div>
            </div>
            <div>
              <div className="text-right text-sm text-neutral-400">Progress</div>
              <div className="mt-2">
                <div
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(precise.progress * 100)}
                  className="w-full bg-white/6 rounded-full h-3 overflow-hidden"
                >
                  <div
                    className="h-3 bg-gradient-to-r from-[#C9A24B] via-[#5B4EFF] to-white/60"
                    style={{ width: `${precise.progress * 100}%`, transition: "width 200ms linear" }}
                  />
                </div>
                <div className="mt-1 text-xs text-neutral-400">{Math.round(precise.progress * 100)}% complete</div>
              </div>
            </div>
          </div>

          <div className="mt-5 text-sm text-neutral-300 flex items-center justify-between">
            <div>
              <span className="text-neutral-400">Started:</span>{" "}
              <span className="text-white">{new Date(startSecRef.current * 1000).toLocaleString()}</span>
            </div>
            <div>
              <span className="text-neutral-400">Time remaining:</span>{" "}
              <span className="text-white">{formatSeconds(precise.remainingSeconds)}</span>
            </div>
          </div>

          {outOfRange && (
            <div className="mt-4 text-xs text-amber-300 bg-amber-900/10 p-2 rounded-md">{outOfRange}</div>
          )}
        </div>

        <div className="w-40 flex-shrink-0">
          <div className="rounded-xl bg-white/5 p-3 text-center">
            <div className="text-xs text-neutral-300">Plan Rate</div>
            <div className="mt-2 text-lg font-semibold text-white">
              {planType === "shareholder"
                ? "10% / month"
                : `${((def.dailyRate ?? 0) * 100).toFixed(2)}% / day`}
            </div>
            <div className="mt-3 text-xs text-neutral-400">Duration: {def.durationSeconds / SECONDS_PER_DAY} days</div>
            <div className="mt-3 text-xs text-neutral-500">Min {fmt.format(def.min)}</div>
            <div className="text-xs text-neutral-500">Max {fmt.format(def.max)}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
