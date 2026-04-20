import { Link } from 'react-router-dom'
import SearchInput from './SearchInput'
import { useNavigate } from 'react-router-dom'

export default function Layout({ children }) {
  const navigate = useNavigate()

  return (
    <>
      <header className="header">
        <div className="header-left">
          <h1><span>⚡</span> A股量化选股</h1>
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
