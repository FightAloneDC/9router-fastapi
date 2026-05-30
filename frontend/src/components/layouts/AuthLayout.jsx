export default function AuthLayout({ children }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-zinc-950 to-slate-950 flex items-center justify-center px-4">
      {children}
    </div>
  )
}
