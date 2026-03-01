// components/data/InteractiveChart.tsx — Plotly with Material dark theme
import Plot from 'react-plotly.js'

interface InteractiveChartProps {
    data?: any[]
    layout?: Record<string, any>
    base64Image?: string
    title?: string
    className?: string
    mode?: 'normal' | 'pro'
}

const darkLayout = (mode: string) => ({
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: '#0B1220',
    font: { color: '#9CA3AF', family: 'Inter, sans-serif', size: 12 },
    xaxis: { gridcolor: '#1E293B', zerolinecolor: '#374151', linecolor: '#1E293B' },
    yaxis: { gridcolor: '#1E293B', zerolinecolor: '#374151', linecolor: '#1E293B' },
    margin: { l: 56, r: 24, t: 36, b: 44 },
    legend: { bgcolor: 'rgba(0,0,0,0)', font: { color: '#9CA3AF', size: 11 } },
    hoverlabel: { bgcolor: '#111827', bordercolor: '#1E293B', font: { color: '#F3F4F6', size: 12 } },
    colorway: mode === 'pro'
        ? ['#D4AF37', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6']
        : ['#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#D4AF37'],
})

export default function InteractiveChart({ data, layout, base64Image, title, className = '', mode = 'normal' }: InteractiveChartProps) {
    if (base64Image) {
        return (
            <div className={`rounded-lg border border-divider overflow-hidden bg-surface-1 elevation-1 ${className}`}>
                {title && (
                    <div className="px-4 py-2.5 border-b border-divider bg-base-bg">
                        <span className="text-caption font-semibold text-text-primary">{title}</span>
                    </div>
                )}
                <div className="p-4 flex justify-center bg-base-bg">
                    <img src={`data:image/png;base64,${base64Image}`} alt={title || 'Chart'} className="max-w-full rounded" />
                </div>
            </div>
        )
    }

    if (data) {
        return (
            <div className={`rounded-lg border border-divider overflow-hidden bg-surface-1 elevation-1 ${className}`}>
                {title && (
                    <div className="px-4 py-2.5 border-b border-divider bg-base-bg">
                        <span className="text-caption font-semibold text-text-primary">{title}</span>
                    </div>
                )}
                <Plot data={data} layout={{ ...darkLayout(mode), ...layout, title: undefined, autosize: true }}
                    config={{
                        responsive: true, displayModeBar: true, displaylogo: false,
                        modeBarButtonsToRemove: ['lasso2d', 'select2d'],
                        toImageButtonOptions: { format: 'png', filename: title || 'chart', scale: 2 }
                    }}
                    style={{ width: '100%', height: '380px' }} useResizeHandler />
            </div>
        )
    }
    return null
}
