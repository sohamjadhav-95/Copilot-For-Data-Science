// components/data/DataTable.tsx — AG Grid with Material dark theme
import { useState, useCallback, useRef, useMemo } from 'react'
import { AgGridReact } from 'ag-grid-react'
import { AllCommunityModule, type ColDef, type GridReadyEvent, type GridApi } from 'ag-grid-community'

interface DataTableProps {
    data: { columns: string[]; data: any[][]; index?: any[] } | null
    title?: string
    className?: string
    compact?: boolean
}

export default function DataTable({ data, title, className = '', compact = false }: DataTableProps) {
    const gridRef = useRef<AgGridReact>(null)
    const [search, setSearch] = useState('')
    const [api, setApi] = useState<GridApi | null>(null)

    const onReady = useCallback((p: GridReadyEvent) => { setApi(p.api); p.api.sizeColumnsToFit() }, [])
    const columnDefs: ColDef[] = useMemo(() =>
        (data?.columns || []).map((c) => ({ field: c, headerName: c, sortable: true, filter: true, resizable: true, minWidth: 90 })),
        [data?.columns]
    )
    const rowData = useMemo(() =>
        (data?.data || []).map((row) => {
            const obj: Record<string, any> = {}
            data?.columns.forEach((c, i) => { obj[c] = row[i] })
            return obj
        }),
        [data]
    )

    if (!data) return null
    const gridH = compact ? 240 : Math.min(420, rowData.length * 36 + 48)

    return (
        <div className={`rounded-lg border border-divider overflow-hidden bg-surface-1 elevation-1 ${className}`}>
            {/* Toolbar */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-divider bg-base-bg">
                {title && <span className="text-caption font-semibold text-text-primary">{title}</span>}
                <div className="flex items-center gap-2 ml-auto">
                    <div className="relative">
                        <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3 h-3 text-text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                        </svg>
                        <input type="text" placeholder="Search..." value={search}
                            onChange={(e) => { setSearch(e.target.value); api?.setGridOption('quickFilterText', e.target.value) }}
                            className="pl-8 pr-3 py-1.5 w-36 text-[11px] material-input rounded-md h-7" />
                    </div>
                    <button onClick={() => api?.exportDataAsCsv({ fileName: title || 'export' })}
                        className="h-7 px-2.5 text-[11px] text-text-muted hover:text-text-primary bg-surface-2 border border-divider rounded-md transition-material cursor-pointer">
                        Export
                    </button>
                </div>
            </div>

            {/* Grid */}
            <div className="ag-theme-alpine-dark" style={{ height: gridH, width: '100%' }}>
                <AgGridReact ref={gridRef} modules={[AllCommunityModule]} columnDefs={columnDefs} rowData={rowData}
                    onGridReady={onReady} pagination={rowData.length > 50} paginationPageSize={50}
                    animateRows suppressCellFocus domLayout={rowData.length <= 8 ? 'autoHeight' : 'normal'} />
            </div>

            {/* Footer */}
            <div className="px-4 py-1.5 border-t border-divider bg-base-bg">
                <span className="text-[10px] text-text-muted">{rowData.length.toLocaleString()} rows × {columnDefs.length} cols</span>
            </div>
        </div>
    )
}
