import { Link } from 'react-router-dom'
import SearchInput from './SearchInput'
import { useNavigate } from 'react-router-dom'

export default function Layout({ children }) {
  const navigate = useNavigate()

  return (
    <>
      <header className="header">
        <div className="header-left">
          <h1>
            <svg className="logo-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
            A股量化选股
          </h1>
          <nav className="nav-links">
            <Link to="/">扫描</Link>
            <Link to="/watchlist">监控</Link>
          </nav>
        </div>
        <SearchInput onSelect={(code) => navigate(`/stock/${code}`)} />
      </header>
      <main className="main">{children}</main>
    </>
  )
}
