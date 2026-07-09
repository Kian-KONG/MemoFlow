import { Link, NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import './Layout.css'

interface LayoutProps {
  children: ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="layout">
      <header className="layout-header">
        <div className="layout-header-inner">
          <Link to="/" className="brand">
            MemoFlow
          </Link>
          <nav className="nav">
            <NavLink to="/" end className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}>
              会议
            </NavLink>
            <NavLink
              to="/settings"
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              设置
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="layout-main">{children}</main>
    </div>
  )
}
