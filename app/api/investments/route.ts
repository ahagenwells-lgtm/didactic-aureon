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
