#!/usr/bin/env bash
set -euo pipefail

BRANCH="scaffold/aureon-starter"
COMMIT_MSG="feat(scaffold): initial Next.js 15 + Tailwind + R3F starter for AUREON"

echo "Fetching origin and creating/updating branch $BRANCH from origin/main..."
git fetch origin
git checkout -B "$BRANCH" origin/main || git checkout -b "$BRANCH"

echo "Writing scaffold files..."

# package.json
cat > package.json <<'EOF'
{
  "name": "didactic-aureon",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "18.2.0",
    "react-dom": "18.2.0",
    "three": "0.163.0",
    "@react-three/fiber": "8.11.0",
    "@react-three/drei": "9.45.0",
    "framer-motion": "10.12.0",
    "gsap": "3.12.2",
    "zustand": "4.5.11",
    "@tanstack/react-query": "5.5.14"
  },
  "devDependencies": {
    "typescript": "5.5.2",
    "tailwindcss": "4.3.1",
    "postcss": "8.4.30",
    "autoprefixer": "10.4.14",
    "eslint": "8.47.0",
    "eslint-config-next": "14.1.0",
    "prisma": "5.15.0"
  }
}
EOF

# next.config.js
cat > next.config.js <<'EOF'
module.exports = {
  experimental: {
    appDir: true,
  },
  reactStrictMode: true,
  images: {
    formats: ["image/avif", "image/webp"],
  },
};
EOF

# tsconfig.json
cat > tsconfig.json <<'EOF'
{
  "compilerOptions": {
    "target": "ES2023",
    "lib": ["DOM", "ES2023"],
    "jsx": "react-jsx",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "types": ["node", "jest"]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
EOF

# tailwind.config.js
cat > tailwind.config.js <<'EOF'
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./pages/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        aureon: {
          900: "#0A0A0C",
          800: "#0F0F11",
          gold: "#C9A24B",
          indigo: "#5B4EFF",
          platinum: "#F5F4F0",
        },
      },
    },
  },
  plugins: [],
};
EOF

# postcss.config.js
cat > postcss.config.js <<'EOF'
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
EOF

# styles
mkdir -p styles
cat > styles/globals.css <<'EOF'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root{
  --bg-obsidian: #0A0A0C;
  --gold: #C9A24B;
  --platinum: #F5F4F0;
  --indigo: #5B4EFF;
}

html, body, #__next {
  height: 100%;
}

body{
  @apply bg-[#070709] text-white;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial;
}

/* reduced motion */
@media (prefers-reduced-motion: reduce){
  *{
    transition: none !important;
    animation: none !important;
  }
}
EOF

# app files and dashboard
mkdir -p "app/(dashboard)" components app/api/investments prisma .github/workflows

cat > app/layout.tsx <<'EOF'
import './globals.css'
import { ReactNode } from 'react'

export const metadata = {
  title: 'Aureon — Luxury Crypto Investment',
  description: 'Aureon demo scaffold',
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  )
}
EOF

cat > app/page.tsx <<'EOF'
export default function Home(){
  return (
    <main className="min-h-screen p-12">
      <h1 className="text-4xl font-semibold">Aureon — Demo Landing</h1>
      <p className="mt-4 text-neutral-300">This is a starter scaffold demonstrating the 3D hero placeholder and the LiveInvestmentTicker in the dashboard.</p>
      <div className="mt-8">
        <a href="/dashboard" className="px-4 py-2 bg-[#C9A24B] text-black rounded-md">Go to Dashboard Demo</a>
      </div>
    </main>
  )
}
EOF

cat > "app/(dashboard)"/page.tsx <<'EOF'
import dynamic from 'next/dynamic'
import Link from 'next/link'

const LiveInvestmentTicker = dynamic(() => import('../../components/LiveInvestmentTicker'), { ssr: false })
const R3FScene = dynamic(() => import('../../components/R3FScene'), { ssr: false })

export default function DashboardPage(){
  // sample props
  const planType = 'gold'
  const principal = 25000
  const startTimestamp = new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString()

  return (
    <main className="min-h-screen p-8">
      <header className="flex items-center justify-between">
        <h2 className="text-2xl font-semibold">Dashboard Demo</h2>
        <Link href="/">Home</Link>
      </header>

      <section className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <div className="w-full h-96 bg-black/30 rounded-xl overflow-hidden">
            <R3FScene />
          </div>
        </div>
        <div>
          <LiveInvestmentTicker planType={planType as any} principalAmount={principal} startTimestamp={startTimestamp} />
        </div>
      </section>
    </main>
  )
}
EOF

# R3F placeholder
cat > components/R3FScene.tsx <<'EOF'
import React, { Suspense } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Html } from '@react-three/drei'

function DummyScene(){
  return (
    <mesh>
      <sphereGeometry args={[1.2, 64, 64]} />
      <meshStandardMaterial color="#C9A24B" metalness={0.8} roughness={0.2} />
    </mesh>
  )
}

export default function R3FScene(){
  return (
    <Canvas camera={{position:[0,0,4]}}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5,5,5]} intensity={1} />
      <Suspense fallback={<Html>Loading 3D...</Html>}>
        <DummyScene />
      </Suspense>
      <OrbitControls enableZoom={false} enablePan={false} />
    </Canvas>
  )
}
EOF

# Full LiveInvestmentTicker component
cat > components/LiveInvestmentTicker.tsx <<'EOF'
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
EOF

# prisma schema
cat > prisma/schema.prisma <<'EOF'
datasource db {
  provider = "postgresql"
  url = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  investments Investment[]
}

model Investment {
  id           String   @id @default(cuid())
  userId       String
  user         User     @relation(fields: [userId], references: [id])
  plan         String
  principal    Float
  startTime    DateTime
  status       String
  createdAt    DateTime @default(now())
}

model AuditLog {
  id        String   @id @default(cuid())
  action    String
  payload   Json?
  createdAt DateTime @default(now())
}
EOF

# API route
mkdir -p app/api/investments
cat > app/api/investments/route.ts <<'EOF'
import { NextResponse } from 'next/server'

export async function GET(){
  // return a sample investment payload (server should return canonical data)
  const sample = {
    id: 'inv_123',
    userId: 'user_1',
    plan: 'gold',
    principal: 25000,
    startTime: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
    status: 'active'
  }

  return NextResponse.json(sample)
}
EOF

# .env.example
cat > .env.example <<'EOF'
{"DATABASE_URL":"postgresql://user:pass@localhost:5432/db","NEXTAUTH_SECRET":"change-me","NEXT_PUBLIC_COINGECKO_KEY":"your_key_here"}
EOF

# ESLint / Prettier / README / License / Ignore
cat > .eslintrc.cjs <<'EOF'
{
  "env": {
    "node": true,
    "browser": true,
    "es2021": true
  },
  "extends": ["next/core-web-vitals","eslint:recommended"],
  "rules": {
    "react/react-in-jsx-scope": "off"
  }
}
EOF

cat > .prettierrc <<'EOF'
{
  "printWidth": 100,
  "singleQuote": true,
  "trailingComma": "es5"
}
EOF

cat > README.md <<'EOF'
# Didactic Aureon

This repo scaffolds a Next.js 15 + TypeScript + Tailwind project for the "Aureon" luxury crypto investment platform demo.

Run locally:

1. git checkout scaffold/aureon-starter
2. npm install
3. cp .env.example .env.local and fill required secrets
4. npm run dev

This scaffold includes a demo dashboard with a placeholder 3D scene and the LiveInvestmentTicker component.
EOF

cat > .gitignore <<'EOF'
node_modules
.env
.env.local
.next
dist
coverage
EOF

cat > LICENSE <<'EOF'
MIT License

Copyright (c) 2026 ahagenwells-lgtm

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
EOF

cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
  push:
    branches: [ main, scaffold/aureon-starter ]
  pull_request:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm run lint
      - run: npm run build
EOF

echo "Adding files to git..."
git add .

echo "Committing..."
git commit -m "$COMMIT_MSG" || echo "Nothing to commit or commit failed (maybe no changes)."

echo "Pushing branch $BRANCH to origin..."
git push -u origin "$BRANCH"

echo "Done. Branch pushed: $BRANCH"
echo "Create a PR via GitHub web UI, or with gh CLI:"
echo "  gh pr create --base main --head scaffold/aureon-starter --title \"$COMMIT_MSG\" --fill"