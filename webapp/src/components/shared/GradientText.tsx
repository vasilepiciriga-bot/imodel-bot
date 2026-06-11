export function GradientText({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={`bg-gradient-to-r from-[#6C47FF] to-[#FF2D78] bg-clip-text text-transparent ${className}`}
    >
      {children}
    </span>
  )
}
