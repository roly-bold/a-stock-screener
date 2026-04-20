import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './components/Dashboard'

const StockDetail = lazy(() => import('./components/StockDetail'))
const Watchlist = lazy(() => import('./components/Watchlist'))
const CompareView = lazy(() => import('./components/CompareView'))

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock/:code" element={
            <Suspense fallback={<div className="empty-state">加载中...</div>}>
              <StockDetail />
            </Suspense>
          } />
          <Route path="/watchlist" element={
            <Suspense fallback={<div className="empty-state">加载中...</div>}>
              <Watchlist />
            </Suspense>
          } />
          <Route path="/compare" element={
            <Suspense fallback={<div className="empty-state">加载中...</div>}>
              <CompareView />
            </Suspense>
          } />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
