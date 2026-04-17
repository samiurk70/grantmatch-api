'use client'

export function AnimatedBackground() {
  return (
    <div className="fixed inset-0 -z-10 overflow-hidden">
      {/* Deep base */}
      <div className="absolute inset-0" style={{ background: '#05070f' }} />

      {/* Animated gradient orbs — smaller on mobile for perf */}
      <div
        className="animate-drift absolute -top-40 -left-40 h-[300px] w-[300px]
          rounded-full opacity-20 blur-[80px] sm:h-[600px] sm:w-[600px] sm:blur-[120px]"
        style={{ background: 'linear-gradient(135deg, #2563eb, #7c3aed)' }}
      />
      <div
        className="animate-drift-slow absolute -bottom-40 -right-40 h-[250px] w-[250px]
          rounded-full opacity-15 blur-[70px] sm:h-[500px] sm:w-[500px] sm:blur-[100px]"
        style={{ background: 'linear-gradient(135deg, #0d9488, #2563eb)' }}
      />
      <div
        className="animate-drift-med absolute left-1/2 top-1/2 h-[200px] w-[200px]
          -translate-x-1/2 -translate-y-1/2 rounded-full opacity-10 blur-[60px]
          sm:h-[400px] sm:w-[400px] sm:blur-[80px]"
        style={{ background: 'linear-gradient(135deg, #7c3aed, #db2777)' }}
      />

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
          `,
          backgroundSize: '60px 60px',
        }}
      />
    </div>
  )
}
