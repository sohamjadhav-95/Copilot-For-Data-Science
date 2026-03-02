// pages/NormalMode.tsx — Normal mode page
import NormalLayout from '../layouts/NormalLayout'
import ChatPanel from '../components/normal/ChatPanel'
import ResultPanel from '../components/normal/ResultPanel'
import ErrorBoundary from '../components/common/ErrorBoundary'

export default function NormalMode() {
    return (
        <NormalLayout
            chatPanel={<ErrorBoundary><ChatPanel /></ErrorBoundary>}
            resultPanel={<ErrorBoundary><ResultPanel /></ErrorBoundary>}
        />
    )
}
