// Type declarations for CSS modules
declare module '*.css' { }

// Type declarations for modules without types
declare module 'react-plotly.js' {
    import { Component } from 'react'

    interface PlotParams {
        data: any[]
        layout?: Record<string, any>
        config?: Record<string, any>
        style?: React.CSSProperties
        useResizeHandler?: boolean
        onInitialized?: (figure: any) => void
        onUpdate?: (figure: any) => void
    }

    export default class Plot extends Component<PlotParams> { }
}
