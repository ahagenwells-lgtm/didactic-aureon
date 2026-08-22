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
