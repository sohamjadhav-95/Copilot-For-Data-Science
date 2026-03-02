// components/common/Skeleton.tsx — Material shimmer skeletons
interface SkeletonProps { className?: string; lines?: number }

export default function Skeleton({ className = '', lines = 1 }: SkeletonProps) {
    return (
        <div className={className}>
            {Array.from({ length: lines }).map((_, i) => (
                <div key={i} className="skeleton h-4 mb-2 last:mb-0"
                    style={{ width: i === lines - 1 && lines > 1 ? '60%' : '100%' }} />
            ))}
        </div>
    )
}

export function CardSkeleton() {
    return (
        <div className="bg-surface-1 border border-divider rounded-xl p-4 elevation-1 animate-fadeIn">
            <div className="skeleton h-5 w-2/3 mb-4" />
            <div className="skeleton h-4 w-full mb-2" />
            <div className="skeleton h-4 w-4/5 mb-2" />
            <div className="skeleton h-4 w-1/2" />
        </div>
    )
}

export function TableSkeleton() {
    return (
        <div className="bg-surface-1 border border-divider rounded-xl p-4 elevation-1">
            <div className="skeleton h-10 w-full mb-3 rounded" />
            {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="skeleton h-9 w-full mb-1 rounded" />
            ))}
        </div>
    )
}
