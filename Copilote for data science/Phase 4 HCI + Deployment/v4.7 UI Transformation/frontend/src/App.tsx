// App.tsx — Root router for the application
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import ProtectedRoute from './components/auth/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import NormalMode from './pages/NormalMode'
import ProWorkspace from './pages/ProWorkspace'
import Settings from './pages/Settings'

export default function App() {
    return (
        <BrowserRouter>
            <Routes>
                {/* Public routes */}
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />

                {/* Protected routes */}
                <Route path="/normal" element={
                    <ProtectedRoute><NormalMode /></ProtectedRoute>
                } />
                <Route path="/pro" element={
                    <ProtectedRoute><ProWorkspace /></ProtectedRoute>
                } />
                <Route path="/settings" element={
                    <ProtectedRoute><Settings /></ProtectedRoute>
                } />

                {/* Default redirect */}
                <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
        </BrowserRouter>
    )
}
