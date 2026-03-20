"use client";

import React, { useState } from "react";
import { authClient } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { Mail, Lock, LogIn, AlertCircle, Eye, EyeOff } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

export default function LoginPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const router = useRouter();

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        try {
            const { error } = await authClient.signIn.email({
                email,
                password,
            });
            if (error) {
                setError(error.message || "Failed to sign in");
            } else {
                router.push("/");
            }
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "An unexpected error occurred.";
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ backgroundColor: 'var(--color-bg-page)', minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px', fontFamily: '"Inter", sans-serif' }}>
            <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, ease: "easeOut" }}
                style={{
                    backgroundColor: 'var(--color-bg-surface)',
                    border: '1px solid var(--color-border-base)',
                    borderRadius: 'var(--radius-lg, 12px)',
                    boxShadow: 'var(--shadow-lg)',
                    width: '100%',
                    maxWidth: '400px',
                    padding: '32px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '24px'
                }}
            >
                <div style={{ textAlign: 'center' }}>
                    <h1 style={{ fontFamily: '"DM Sans", sans-serif', color: 'var(--color-text-primary)', fontSize: '28px', fontWeight: 700, margin: '0 0 8px 0' }}>Welcome Back</h1>
                    <p style={{ color: 'var(--color-text-secondary)', fontSize: '15px', margin: 0 }}>Log in to your intelligence dashboard</p>
                </div>

                {error && (
                    <motion.div 
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '12px 16px',
                            backgroundColor: 'var(--color-error-bg)',
                            border: '1px solid var(--color-error-border)',
                            borderRadius: 'var(--radius-md, 8px)',
                            color: 'var(--color-error)',
                            fontSize: '14px',
                            fontWeight: 500
                        }}
                    >
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </motion.div>
                )}

                <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={{ color: 'var(--color-text-body)', fontSize: '14px', fontWeight: 500 }}>Email Address</label>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            border: '1px solid var(--color-border-base)',
                            backgroundColor: 'var(--color-bg-muted)',
                            borderRadius: 'var(--radius-md, 8px)',
                            padding: '0 12px',
                            height: '44px'
                        }}>
                            <Mail size={18} style={{ color: 'var(--color-text-muted)', marginRight: '10px' }} />
                            <input
                                type="email"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="harshitpatil1924@gmail.com"
                                style={{
                                    flex: 1,
                                    border: 'none',
                                    outline: 'none',
                                    background: 'transparent',
                                    color: 'var(--color-text-primary)',
                                    fontSize: '15px',
                                    width: '100%'
                                }}
                                required
                            />
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <label style={{ color: 'var(--color-text-body)', fontSize: '14px', fontWeight: 500 }}>Password</label>
                        </div>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            border: '1px solid var(--color-border-base)',
                            backgroundColor: 'var(--color-bg-muted)',
                            borderRadius: 'var(--radius-md, 8px)',
                            padding: '0 12px',
                            height: '44px'
                        }}>
                            <Lock size={18} style={{ color: 'var(--color-text-muted)', marginRight: '10px' }} />
                            <input
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                style={{
                                    flex: 1,
                                    border: 'none',
                                    outline: 'none',
                                    background: 'transparent',
                                    color: 'var(--color-text-primary)',
                                    fontSize: '15px',
                                    width: '100%'
                                }}
                                required
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: '4px',
                                    color: 'var(--color-text-muted)',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                                title={showPassword ? "Hide password" : "Show password"}
                            >
                                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <button 
                        type="submit" 
                        disabled={loading}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '8px',
                            backgroundColor: 'var(--color-accent)',
                            color: '#FFFFFF',
                            border: 'none',
                            borderRadius: 'var(--radius-md, 8px)',
                            height: '48px',
                            fontSize: '15px',
                            fontWeight: 600,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.7 : 1,
                            transition: 'all 0.2s',
                            marginTop: '8px'
                        }}
                    >
                        <LogIn size={18} />
                        {loading ? 'Authenticating...' : 'Sign In'}
                    </button>
                </form>

                <div style={{ textAlign: 'center', borderTop: '1px solid var(--color-border-base)', paddingTop: '20px', marginTop: '4px' }}>
                    <p style={{ color: 'var(--color-text-secondary)', fontSize: '14px', margin: 0 }}>
                        Don&apos;t have an account?{' '}
                        <Link href="/signup" style={{ color: 'var(--color-accent)', fontWeight: 600, textDecoration: 'none' }}>
                            Sign up
                        </Link>
                    </p>
                </div>
            </motion.div>
        </div>
    );
}
