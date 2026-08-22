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
