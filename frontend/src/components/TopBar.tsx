'use client';

import React from 'react';
import {BarChart2, Scale, Globe2, Sun, Moon, User, LogOut, PanelLeftOpen, PanelLeftClose} from 'lucide-react';
import {useTheme} from '@/components/ThemeProvider';
import {authClient} from '@/lib/auth-client';
import {useRouter} from 'next/navigation';

interface TopBarProps {
  domain: 'finance' | 'law' | 'global';
  title?: string;
  showSidebarToggle?: boolean;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

export default function TopBar({
  domain,
  title,
  showSidebarToggle = false,
  isSidebarOpen = false,
  onToggleSidebar,
}: TopBarProps) {
  const {theme, toggle} = useTheme();
  const {data: session} = authClient.useSession();
  const router = useRouter();

  const handleLogout = async () => {
    await authClient.signOut();
    router.push('/login');
  };

  return (
    <header
      style={{
        height: '56px',
        minHeight: '56px',
        backgroundColor: 'var(--color-bg-surface)',
        borderBottom: '1px solid var(--color-border-base)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 24px',
        flexShrink: 0,
      }}
    >
      {/* Domain badge + title */}
      <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
        {showSidebarToggle && (
          <button
            onClick={onToggleSidebar}
            aria-label={isSidebarOpen ? 'Close sidebar' : 'Open sidebar'}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '44px',
              height: '44px',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: 'transparent',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
              transition: 'background-color 150ms ease-out',
            }}
          >
            {isSidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
          </button>
        )}

        {/* Domain badge pill (ui.md Section 9.3) */}
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--color-bg-accent)',
            color: 'var(--color-text-accent)',
            fontSize: '13px',
            fontWeight: 600,
            letterSpacing: '0.03em',
          }}
        >
          {domain === 'finance' ? (
            <BarChart2 size={14} aria-hidden="true" />
          ) : domain === 'law' ? (
            <Scale size={14} aria-hidden="true" />
          ) : (
            <Globe2 size={14} aria-hidden="true" />
          )}
          {domain.toUpperCase()}
        </span>

        {title && (
          <span
            style={{
              fontSize: '15px',
              color: 'var(--color-text-secondary)',
              fontFamily: 'DM Sans, sans-serif',
            }}
          >
            {title}
          </span>
        )}
      </div>

      <div style={{display: 'flex', alignItems: 'center', gap: '16px'}}>
        {/* Theme toggle */}
      <button
        onClick={toggle}
        aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '44px',
          height: '44px',
          borderRadius: 'var(--radius-md)',
          border: 'none',
          backgroundColor: 'transparent',
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
          transition: 'background-color 150ms ease-out',
        }}
      >
        {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
      </button>

      {/* User Profile & Logout */}
      {session && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '12px',
          marginLeft: '8px', paddingLeft: '16px', borderLeft: '1px solid var(--color-border-base)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <div style={{
              width: '28px', height: '28px',
              borderRadius: '50%', backgroundColor: 'var(--color-bg-muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--color-text-secondary)'
            }}>
              <User size={14} />
            </div>
            <span style={{ fontSize: '13px', color: 'var(--color-text-body)', fontWeight: 500 }}>
              {session.user.name || session.user.email}
            </span>
          </div>
          <button
            onClick={handleLogout}
            aria-label="Log out"
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              width: '44px', height: '44px', borderRadius: 'var(--radius-md)',
              border: 'none', backgroundColor: 'transparent',
              color: 'var(--color-text-secondary)', cursor: 'pointer',
            }}
          >
            <LogOut size={16} />
          </button>
        </div>
      )}
      </div>
    </header>
  );
}
