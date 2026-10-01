import React, { useState } from 'react';
import { ShoppingCart, ShieldCheck, Sparkles, Terminal, ArrowRight, CheckCircle2, RefreshCw, KeyRound, ExternalLink, AlertTriangle } from 'lucide-react';

function extractText(content) {
  if (!content) return "Action completed.";
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.map(part => (typeof part === 'object' ? part.text || '' : String(part))).join('\n');
  }
  return content.text || JSON.stringify(content);
}

export default function App() {
  const [sessionId] = useState(() => "session-" + Math.random().toString(36).substring(2, 9));
  const [mode, setMode] = useState("deterministic");
  const [prompt, setPrompt] = useState("Search catalog for Rainbow Glitter High Heels, create a cart for 3 items, checkout with shipping to 100 Market St, San Francisco, CA 94105, and complete the order directly.");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState([]);
  const [stateSnapshot, setStateSnapshot] = useState({ cart: null, checkout: null, order: null });

  // 3DS2 Challenge Modal State
  const [showChallenge, setShowChallenge] = useState(false);
  const [challengeData, setChallengeData] = useState(null);
  const [otp, setOtp] = useState("");
  const [verificationError, setVerificationError] = useState("");

  const syncState = (data) => {
    if (data.state_snapshot) {
      setStateSnapshot(data.state_snapshot);
      const chk = data.state_snapshot.checkout;
      if (chk && chk.status === 'requires_action' && chk.action_challenge) {
        setChallengeData(chk.action_challenge);
        setOtp(""); // Keep field clean/blank for manual entry
        setVerificationError("");
        setShowChallenge(true);
      } else if (chk && chk.status === 'completed') {
        setShowChallenge(false);
      }
    }
  };

  const handleSend = async () => {
    if (!prompt.trim() || loading) return;
    const userPrompt = prompt;
    setLoading(true);
    setMessages(prev => [...prev, { role: 'user', content: userPrompt, mode }]);

    try {
      const res = await fetch("/api/v1/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, mode, prompt: userPrompt })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Execution failed");

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: extractText(data.reply || data.response),
        mode: data.agent_name || mode,
        actions: data.actions || []
      }]);
      syncState(data);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'error', content: err.message, mode }]);
    } finally {
      setLoading(false);
    }
  };

  const handleResolve3DS2 = async () => {
    if (!otp.trim()) {
      setVerificationError("Please enter the 6-digit OTP passcode.");
      return;
    }
    setVerificationError("");

    try {
      const res = await fetch("/api/v1/ucp/actions/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, challenge_id: challengeData.challenge_id, otp_code: otp.trim() })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Verification failed");

      setShowChallenge(false);
      setStateSnapshot(prev => ({
        ...prev,
        order: data.order,
        checkout: { ...prev.checkout, status: 'completed' }
      }));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `✔ 3DS2 Step-Up Authenticated! Order placed successfully: ${data.order.order_number}`,
        mode: '3ds2_security_gateway'
      }]);
    } catch (e) {
      setVerificationError(e.message);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'system-ui, sans-serif', backgroundColor: '#0f172a', color: '#f8fafc' }}>
      {/* 3DS2 Interactive Challenge Dialog Modal */}
      {showChallenge && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#1e293b', border: '1px solid #38bdf8', borderRadius: '10px', padding: '24px', width: '400px', boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', color: '#38bdf8' }}>
              <KeyRound size={22} />
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>UCP 3DS2 Step-Up Challenge</h3>
            </div>
            <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: 1.4, margin: '0 0 12px 0' }}>
              {challengeData?.message || "High-value transaction requires cardholder authentication."}
            </p>
            <div style={{ backgroundColor: '#0f172a', padding: '10px', borderRadius: '6px', fontSize: '12px', marginBottom: '12px', display: 'flex', justifyContent: 'space-between' }}>
              <span>Transaction Amount:</span>
              <span style={{ fontWeight: 600, color: '#38bdf8' }}>${challengeData?.amount?.toFixed(2)} {challengeData?.currency}</span>
            </div>
            
            <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 6px 0' }}>
              📲 Passcode dispatched via SMS/Push! (Check your Uvicorn console)
            </p>
            
            <input
              type="text"
              maxLength={6}
              placeholder="••••••"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              style={{
                width: '93%',
                padding: '10px',
                backgroundColor: '#0f172a',
                border: verificationError ? '1px solid #ef4444' : '1px solid #475569',
                color: '#fff',
                borderRadius: '6px',
                letterSpacing: '8px',
                textAlign: 'center',
                fontSize: '20px',
                fontWeight: 700
              }}
            />

            {verificationError && (
              <div style={{ color: '#ef4444', fontSize: '12px', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <AlertTriangle size={14} /> {verificationError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '18px' }}>
              <button
                onClick={() => setShowChallenge(false)}
                style={{ padding: '8px 14px', backgroundColor: '#475569', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' }}
              >
                Cancel (Test via Chat)
              </button>
              <button
                onClick={handleResolve3DS2}
                style={{ padding: '8px 16px', backgroundColor: '#0284c7', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '13px' }}
              >
                Verify & Complete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Left Chat Surface */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRight: '1px solid #334155' }}>
        <header style={{ padding: '16px 24px', borderBottom: '1px solid #334155', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={20} color="#60a5fa" /> Google UCP Shopping Experience (v2026-08-25)
            </h1>
            <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Session ID: {sessionId}</p>
          </div>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            style={{ backgroundColor: '#1e293b', color: '#fff', border: '1px solid #475569', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
          >
            <option value="deterministic">Deterministic Engine (0 Tokens)</option>
            <option value="gemini">Gemini 2.5 (Autonomous Agent)</option>
          </select>
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {messages.length === 0 && (
            <div style={{ margin: 'auto', textAlign: 'center', color: '#64748b', maxWidth: '420px' }}>
              <Terminal size={40} style={{ margin: '0 auto 12px auto' }} />
              <p style={{ fontSize: '14px', lineHeight: 1.5 }}>
                Submit a shopping intent. Transactions exceeding $100 trigger an elevated-risk dynamic 3DS2 challenge, verifiable via modal or natural-language prompt.
              </p>
            </div>
          )}
          {messages.map((m, idx) => (
            <div key={idx} style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '85%',
              backgroundColor: m.role === 'user' ? '#1d4ed8' : m.role === 'error' ? '#991b1b' : '#1e293b',
              padding: '12px 16px',
              borderRadius: '8px',
              border: '1px solid #334155'
            }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: '#94a3b8', marginBottom: '4px' }}>
                {m.role === 'user' ? 'Buyer Intent' : `Agent (${m.mode})`}
              </div>
              <div style={{ fontSize: '14px', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{m.content}</div>
            </div>
          ))}
        </div>

        <div style={{ padding: '16px 24px', borderTop: '1px solid #334155', display: 'flex', gap: '12px' }}>
          <textarea
            rows={2}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            style={{ flex: 1, backgroundColor: '#1e293b', color: '#fff', border: '1px solid #475569', borderRadius: '6px', padding: '8px 12px', fontSize: '14px' }}
          />
          <button
            onClick={handleSend}
            disabled={loading}
            style={{ padding: '0 20px', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            {loading ? <RefreshCw className="animate-spin" size={16} /> : <ArrowRight size={16} />}
            {loading ? 'Executing...' : 'Send'}
          </button>
        </div>
      </div>

      {/* Right Protocol State Inspector */}
      <div style={{ width: '420px', display: 'flex', flexDirection: 'column', backgroundColor: '#0b1120', overflowY: 'auto', padding: '16px', gap: '16px' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid #334155', paddingBottom: '12px' }}>
          <ShieldCheck size={18} color="#4ade80" />
          <h2 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>Protocol State Inspector</h2>
        </header>

        {/* UCP Cart & Permalink */}
        <div style={{ backgroundColor: '#1e293b', padding: '12px', borderRadius: '6px', border: '1px solid #334155' }}>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '12px', color: '#94a3b8' }}>UCP CART & PERMALINK (#523)</h3>
          {stateSnapshot.cart ? (
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600 }}>Subtotal: ${stateSnapshot.cart.subtotal?.toFixed(2)} {stateSnapshot.cart.currency}</div>
              {stateSnapshot.cart.permalink && (
                <div style={{ marginTop: '8px', fontSize: '11px', wordBreak: 'break-all', backgroundColor: '#0f172a', padding: '6px', borderRadius: '4px' }}>
                  <a href={stateSnapshot.cart.permalink} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    🔗 Recover Cart URL <ExternalLink size={11} />
                  </a>
                </div>
              )}
              {/* Policies Snapshot Display (#572) */}
              <div style={{ marginTop: '8px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {stateSnapshot.cart.policies?.map((pol, pIdx) => (
                  <span key={pIdx} style={{ backgroundColor: '#0369a1', fontSize: '10px', padding: '2px 6px', borderRadius: '3px' }}>
                    ✔ {pol.summary}
                  </span>
                ))}
              </div>
            </div>
          ) : <span style={{ fontSize: '12px', color: '#64748b' }}>No active cart</span>}
        </div>

        {/* Checkout Session */}
        <div style={{ backgroundColor: '#1e293b', padding: '12px', borderRadius: '6px', border: '1px solid #334155' }}>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '12px', color: '#94a3b8' }}>CHECKOUT & STEP-UP (3DS2)</h3>
          {stateSnapshot.checkout ? (
            <div style={{ fontSize: '12px' }}>
              <div>Status: <span style={{ color: stateSnapshot.checkout.status === 'requires_action' ? '#f59e0b' : '#4ade80', fontWeight: 600 }}>{stateSnapshot.checkout.status}</span></div>
              {stateSnapshot.checkout.status === 'requires_action' && (
                <button
                  onClick={() => setShowChallenge(true)}
                  style={{ marginTop: '8px', padding: '6px 10px', backgroundColor: '#d97706', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '11px', fontWeight: 600 }}
                >
                  Open 3DS2 Challenge Modal
                </button>
              )}
            </div>
          ) : <span style={{ fontSize: '12px', color: '#64748b' }}>Checkout uninitialized</span>}
        </div>

        {/* Confirmed Order & Attribution */}
        <div style={{ backgroundColor: '#1e293b', padding: '12px', borderRadius: '6px', border: '1px solid #334155' }}>
          <h3 style={{ margin: '0 0 6px 0', fontSize: '12px', color: '#94a3b8' }}>SHOPIFY ORDER & ATTRIBUTION (#391)</h3>
          {stateSnapshot.order ? (
            <div style={{ fontSize: '12px' }}>
              <div style={{ color: '#4ade80', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> Confirmed: {stateSnapshot.order.order_number}
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '4px' }}>
                Source: {stateSnapshot.order.attribution?.source_platform || 'google_gemini_ui'} | Campaign: {stateSnapshot.order.attribution?.campaign || 'v2026-08-25'}
              </div>
              {stateSnapshot.order.admin_url && (
                <a href={stateSnapshot.order.admin_url} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', display: 'inline-block', marginTop: '6px' }}>
                  View in Shopify Admin ↗
                </a>
              )}
            </div>
          ) : <span style={{ fontSize: '12px', color: '#64748b' }}>No order created</span>}
        </div>
      </div>
    </div>
  );
}