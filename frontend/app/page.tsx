"use client";

import { useState, useEffect, useCallback, useRef } from "react";
// import ReactMarkdown from "react-markdown"; // AI feature paused
import {
  Search, Star,
  Info, ExternalLink, X, ShieldCheck, ChevronDown, ChevronUp, Copy
} from "lucide-react";

// --- Types ---

type Holding = {
  index: number;
  code: string;
  name: string;
  weight_pct: number;
  change_pct: number | null;
  contribution: number | null;
};

type ApiResult = {
  fund_code: string;
  fund_name?: string;
  quarter: string;
  time: string;
  top10_weight_pct: number | null;
  estimated_change: number | null;
  holdings: Holding[];
};

type SearchResult = {
  code: string;
  name: string;
};

// --- Styles ---

const styles = {
  container: {
    maxWidth: 640,
    margin: "0 auto",
    padding: "1.5rem 1.25rem",
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    background: "#0a0a0c",
    minHeight: "100vh",
    color: "#e4e4e7",
    lineHeight: 1.5,
  },
  header: {
    marginBottom: "0.5rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "0.5rem",
    flexWrap: "nowrap" as const,
    padding: "0.5rem 0",
  },
  navLink: {
    fontSize: "0.85rem",
    color: "#a1a1aa",
    textDecoration: "none",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: "0.3rem",
    transition: "all 0.2s",
    padding: "0.2rem 0.5rem",
    borderRadius: "0.5rem",
  },
  aiBtn: {
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    padding: "0.3rem 0.7rem",
    borderRadius: "2rem",
    background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
    color: "#fff",
    fontSize: "0.8rem",
    fontWeight: 700,
    cursor: "pointer",
    border: "none",
    boxShadow: "0 0 15px rgba(139, 92, 246, 0.3)",
    animation: "pulse 3s infinite ease-in-out",
  },
  hotFundItem: {
    padding: "0.6rem 1.25rem", 
    borderBottom: "1px solid #27272a", 
    cursor: "pointer", 
    display: "flex", 
    justifyContent: "space-between", 
    alignItems: "center",
    fontSize: "0.85rem",
    color: "#71717a",
    transition: "all 0.2s",
  },
  aiPanel: {
    background: "rgba(18, 18, 22, 0.8)",
    backdropFilter: "blur(12px)",
    border: "1px solid rgba(139, 92, 246, 0.2)",
    borderRadius: "1rem",
    padding: "1.25rem",
    marginTop: "0.75rem",
    marginBottom: "1rem",
  },
  aiSection: {
    marginBottom: "1rem",
  },
  aiTitle: {
    color: "#a78bfa",
    fontSize: "0.9rem",
    fontWeight: 800,
    marginBottom: "0.4rem",
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
  },
  aiContent: {
    fontSize: "0.9rem",
    color: "#d4d4d8",
    lineHeight: 1.6,
  },
  hotFundLabel: {
    padding: "0.75rem 1.25rem 0.25rem",
    fontSize: "0.75rem",
    color: "#71717a",
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  },
  title: {
    fontSize: "1.25rem", // Slightly smaller title
    fontWeight: 800,
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    color: "#fff",
    letterSpacing: "-0.02em",
    whiteSpace: "nowrap" as const,
  },
  heatBarContainer: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    background: "#18181b",
    padding: "0.35rem 0.6rem",
    borderRadius: "1rem",
    border: "1px solid #27272a",
    flexShrink: 0, // Ensure it doesn't shrink
  },
  heatBar: {
    height: "6px",
    width: "70px",
    background: "#27272a",
    borderRadius: "3px",
    overflow: "hidden",
    display: "flex",
    boxShadow: "inset 0 1px 2px rgba(0,0,0,0.5)",
  },
  card: {
    background: "#121216",
    border: "1px solid #27272a",
    borderRadius: "0.875rem",
    padding: "0.75rem", // Further reduced from 1rem
    marginBottom: "0.6rem", // Further reduced from 0.75rem
    boxShadow: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
  },
  inputContainer: {
    position: "relative" as const,
    marginBottom: "0.6rem", // Unified from 1.25rem
    width: "100%",
  },
  input: {
    width: "100%",
    padding: "0.8rem 1rem 0.8rem 3rem",
    border: "1px solid #27272a",
    borderRadius: "0.75rem",
    background: "#121216",
    color: "#fff",
    fontSize: "1rem",
    outline: "none",
    transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
    boxSizing: "border-box" as const,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse" as const,
    fontSize: "0.95rem",
  },
  th: {
    textAlign: "left" as const,
    padding: "0.6rem 0.2rem", // Further reduced horizontal padding
    color: "#a1a1aa", // Brighter from #71717a
    fontWeight: 700, // Heavier weight
    fontSize: "0.85rem", // Larger from 0.8rem
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    borderBottom: "1px solid #27272a",
  },
  td: {
    padding: "0.6rem 0.2rem", // Further reduced horizontal padding
    borderBottom: "1px solid #1a1a20",
  },
  watchlist: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "0.5rem",
    marginBottom: "0.6rem", // Unified from 1.5rem
    transition: "max-height 0.3s ease-out",
    overflow: "hidden",
  },
  watchlistItem: {
    padding: "0.4rem 0.8rem",
    background: "#18181b",
    border: "1px solid #27272a",
    borderRadius: "2rem",
    fontSize: "0.85rem",
    cursor: "pointer",
    color: "#a1a1aa",
    transition: "all 0.2s",
    whiteSpace: "nowrap" as const,
  },
  watchlistExpandBtn: {
    padding: "0.4rem 0.2rem",
    background: "transparent",
    border: "none",
    color: "#3b82f6",
    fontSize: "0.85rem",
    fontWeight: 600,
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "0.2rem",
    flexShrink: 0,
  },
  footer: {
    marginTop: "1.25rem",
    paddingTop: "0.75rem",
    fontSize: "0.8rem",
    color: "#71717a",
    lineHeight: 1.6,
  },
  mvpBanner: {
    background: "rgba(59, 130, 246, 0.06)",
    border: "1px solid rgba(59, 130, 246, 0.2)",
    borderRadius: "0.875rem",
    padding: "0.85rem 1rem",
    margin: "0.75rem 0 0.9rem",
    color: "#d4d4d8",
  },
  mvpBannerTitle: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    fontWeight: 700,
    color: "#93c5fd",
    marginBottom: "0.35rem",
    letterSpacing: "-0.01em",
  },
  mvpBannerText: {
    fontSize: "0.85rem",
    color: "#a1a1aa",
    lineHeight: 1.7,
  },
  mvpBannerLink: {
    color: "#3b82f6",
    textDecoration: "none",
    fontWeight: 600,
  }
};

// --- Bubble Component ---
const Bubble = ({ message, visible }: { message: string, visible: boolean }) => {
  if (!visible) return null;

  const style = {
    position: "fixed" as const,
    top: "3rem",
    left: "50%",
    transform: "translateX(-50%)",
    padding: "0.75rem 1.25rem",
    background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
    color: "#fff",
    borderRadius: "2rem",
    zIndex: 100,
    boxShadow: "0 4px 15px rgba(0, 0, 0, 0.2)",
    fontSize: "0.9rem",
    fontWeight: 600,
    animation: "fadeInOut 3s ease-in-out forwards",
  };

  return <div style={style}>{message}</div>;
};


// --- Components ---

export default function Home() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ApiResult | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [watchlist, setWatchlist] = useState<SearchResult[]>([]);
  const [isWatchlistExpanded, setIsWatchlistExpanded] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [bubble, setBubble] = useState<{ message: string; visible: boolean }>({ message: "", visible: false });
  const bubbleTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const autoRefreshRef = useRef<NodeJS.Timeout | null>(null);
  const currentFundRef = useRef<SearchResult | null>(null);
  
  // V2 AI States — paused, teaser mode
  // const [aiLoading, setAiLoading] = useState(false);
  // const [aiData, setAiData] = useState<any>(null);
  // const [aiText, setAiText] = useState("");
  // const [activeAiFundCode, setActiveAiFundCode] = useState<string | null>(null);
  // const aiTypingTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [showAiTeaser, setShowAiTeaser] = useState(false);
  const [showHotPanel, setShowHotPanel] = useState(false);
  const [hotFunds, setHotFunds] = useState<SearchResult[]>([]);
  const searchRef = useRef<HTMLDivElement>(null);
  const watchlistRef = useRef<HTMLDivElement>(null);
  const [hasWatchlistOverflow, setHasWatchlistOverflow] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
  const SALES_EMAIL = process.env.NEXT_PUBLIC_SALES_EMAIL || "sean.zhang.fintech.edu@gmail.com";

  const showBubble = (message: string) => {
    if (bubbleTimeoutRef.current) {
      clearTimeout(bubbleTimeoutRef.current);
    }
    setBubble({ message, visible: true });
    bubbleTimeoutRef.current = setTimeout(() => {
      setBubble({ message: "", visible: false });
    }, 3000);
  };

  // Initial load
  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("fund_watchlist");
    if (saved) {
      try { setWatchlist(JSON.parse(saved)); } catch (e) {}
    }
    fetchHotFunds();

    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setShowSearch(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []); // Only once on mount

  // Trading hours check (CST = UTC+8): 9:30-11:30, 13:00-15:00, weekdays only
  const isTradingHours = () => {
    const now = new Date();
    const cst = new Date(now.getTime() + 8 * 60 * 60 * 1000);
    const day = cst.getUTCDay();
    if (day === 0 || day === 6) return false;
    const t = cst.getUTCHours() * 60 + cst.getUTCMinutes();
    return (t >= 9 * 60 + 30 && t <= 11 * 60 + 30) || (t >= 13 * 60 && t <= 15 * 60);
  };

  // Auto-refresh every 60s during trading hours
  useEffect(() => {
    const schedule = () => {
      autoRefreshRef.current = setTimeout(async () => {
        if (currentFundRef.current && isTradingHours()) {
          await silentRefresh(currentFundRef.current);
        }
        schedule();
      }, 60000);
    };
    schedule();
    return () => { if (autoRefreshRef.current) clearTimeout(autoRefreshRef.current); };
  }, []);

  const silentRefresh = async (fund: SearchResult) => {
    try {
      const res = await fetch(`${API_BASE}/api/fund/${fund.code}`);
      const json = await res.json();
      if (res.ok) setData(json);
    } catch (e) {}
  };

  // Check watchlist overflow
  useEffect(() => {
    const checkOverflow = () => {
      if (watchlistRef.current) {
        // One row is roughly 38px
        const isOverflowing = watchlistRef.current.scrollHeight > 40;
        setHasWatchlistOverflow(isOverflowing);
      }
    };

    checkOverflow();
    window.addEventListener("resize", checkOverflow);
    return () => window.removeEventListener("resize", checkOverflow);
  }, [watchlist]);

  const fetchHotFunds = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/hot-funds`);
      const json = await res.json();
      setHotFunds(json);
    } catch (e) {}
  };

  // AI analysis paused — teaser mode
  // const fetchAiAnalysis = async (fundCode: string) => { ... };

  const handleSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(q)}`);
      const json = await res.json();
      setSearchResults(json);
      setShowSearch(true);
    } catch (e) {}
  }, [API_BASE]);

  const fetchFund = async (fund: SearchResult) => {
    currentFundRef.current = fund;
    // Auto-add to recently viewed: move to front, cap at 10
    setWatchlist(prev => {
      const updated = [fund, ...prev.filter(f => f.code !== fund.code)].slice(0, 10);
      localStorage.setItem("fund_watchlist", JSON.stringify(updated));
      return updated;
    });
    setLoading(true);
    setError(null);
    setShowSearch(false);
    setCode(`${fund.name} (${fund.code})`);
    try {
      const res = await fetch(`${API_BASE}/api/fund/${fund.code}`);
      const json = await res.json();
      if (!res.ok) {
        setError(json.detail || "查询失败");
        return;
      }
      setData(json);
      setShowHotPanel(false);
    } catch (err) {
      setError("网络错误，请稍后再试");
    } finally {
      setLoading(false);
    }
  };

  const toggleWatchlist = (fund: SearchResult) => {
    const exists = watchlist.find(f => f.code === fund.code);
    const newList = exists ? watchlist.filter(f => f.code !== fund.code) : [...watchlist, fund];
    setWatchlist(newList);
    localStorage.setItem("fund_watchlist", JSON.stringify(newList));
  };

  if (!mounted) return null;

  return (
    <main style={styles.container}>
      <Bubble message={bubble.message} visible={bubble.visible} />
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.title}>
          <ShieldCheck size={24} color="#3b82f6" />
          基金透视
        </h1>

        <nav style={{ display: "flex", alignItems: "center", gap: "0.8rem" }}>
          <a
            href="#"
            style={{ ...styles.navLink, color: showHotPanel ? "#f59e0b" : "#a1a1aa" }}
            onClick={(e) => { e.preventDefault(); setShowHotPanel(v => !v); }}
          >
            热门基金
          </a>
        </nav>
      </header>

      {/* Search */}
      <div style={styles.inputContainer} ref={searchRef}>
        <div style={{ position: "absolute", left: "1.1rem", top: "50%", transform: "translateY(-50%)", color: "#52525b" }}>
          <Search size={20} />
        </div>
        <input
          style={styles.input}
          placeholder="搜索基金代码或名称"
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            handleSearch(e.target.value);
          }}
          onFocus={(e) => {
            e.target.select();
            setShowSearch(true);
          }}
        />
        
        {showSearch && (searchResults.length > 0 || hotFunds.length > 0) && (
          <div style={{
            position: "absolute", top: "100%", left: 0, right: 0,
            background: "#18181b", border: "1px solid #27272a", borderRadius: "0.75rem",
            marginTop: "0.5rem", zIndex: 10, maxHeight: "320px", overflowY: "auto",
            boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
          }}>
            {searchResults.length > 0 && (
              <>
                <div style={styles.hotFundLabel}>搜索结果</div>
                {searchResults.map((f) => (
                  <div
                    key={f.code}
                    style={{ padding: "0.9rem 1.25rem", borderBottom: "1px solid #27272a", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
                    onClick={() => fetchFund(f)}
                  >
                    <div>
                      <span style={{ fontWeight: 600, color: "#fff", marginRight: "0.6rem" }}>{f.code}</span>
                      <span style={{ color: "#a1a1aa" }}>{f.name}</span>
                    </div>
                    <div onClick={(e) => { e.stopPropagation(); toggleWatchlist(f); }}>
                      {watchlist.find(w => w.code === f.code) ? <Star size={18} fill="#f59e0b" color="#f59e0b" /> : <Star size={18} color="#3f3f46" />}
                    </div>
                  </div>
                ))}
              </>
            )}
            {hotFunds.length > 0 && (
              <>
                <div style={{ ...styles.hotFundLabel, ...(searchResults.length > 0 ? { borderTop: "1px solid #27272a", padding: "0.5rem 1.25rem 0.25rem" } : {}) }}>热门基金</div>
                {hotFunds.map((f) => (
                  <div
                    key={f.code}
                    style={styles.hotFundItem}
                    onClick={() => { fetchFund(f); setShowSearch(false); }}
                  >
                    <div>
                      <span style={{ marginRight: "0.6rem" }}>{f.code}</span>
                      <span>{f.name}</span>
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>

      {watchlist.length > 0 && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: "0.2rem", marginBottom: "0.6rem" }}>
          <div 
            ref={watchlistRef}
            style={{
              ...styles.watchlist,
              marginBottom: 0,
              maxHeight: isWatchlistExpanded ? "1000px" : "38px",
              flex: 1,
            }}
          >
            {watchlist.map(f => (
              <div key={f.code} style={styles.watchlistItem} onClick={() => fetchFund(f)}>
                {f.name}
              </div>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "0.2rem", flexShrink: 0 }}>
            {(hasWatchlistOverflow || isWatchlistExpanded) && (
              <button
                style={{ ...styles.watchlistExpandBtn }}
                onClick={() => setIsWatchlistExpanded(!isWatchlistExpanded)}
              >
                {isWatchlistExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            )}
            <button
              style={{ ...styles.watchlistExpandBtn, color: "#ef4444" }}
              onClick={() => { setWatchlist([]); localStorage.removeItem("fund_watchlist"); setIsWatchlistExpanded(false); }}
            >
              <X size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Hot funds panel — landing (no fund) or toggled from nav */}
      {(showHotPanel || !data) && hotFunds.length > 0 && !loading && (
        <div style={{ ...styles.card, padding: "0.5rem 0", marginBottom: "0.6rem" }}>
          <div style={{ padding: "0.5rem 1rem 0.25rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#71717a", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>
              热门基金 · 近1月涨幅
            </span>
            {data && (
              <button onClick={() => setShowHotPanel(false)} style={{ background: "none", border: "none", color: "#52525b", cursor: "pointer", fontSize: "0.8rem" }}>收起</button>
            )}
          </div>
          {hotFunds.map((f, i) => (
            <div
              key={f.code}
              style={{ ...styles.hotFundItem, padding: "0.55rem 1rem" }}
              onClick={() => fetchFund(f)}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "0.75rem", fontWeight: 700, color: i < 3 ? "#f59e0b" : "#3f3f46", width: "1rem", textAlign: "center" as const }}>{i + 1}</span>
                <div>
                  <span style={{ color: "#e4e4e7", fontWeight: 600, marginRight: "0.5rem" }}>{f.name}</span>
                  <span style={{ fontSize: "0.75rem", color: "#52525b" }}>{f.code}</span>
                </div>
              </div>
              <Star
                size={16}
                fill={watchlist.find(w => w.code === f.code) ? "#f59e0b" : "none"}
                color={watchlist.find(w => w.code === f.code) ? "#f59e0b" : "#3f3f46"}
                style={{ cursor: "pointer", flexShrink: 0 }}
                onClick={(e) => { e.stopPropagation(); toggleWatchlist(f); }}
              />
            </div>
          ))}
        </div>
      )}

      {error && (
        <div style={{ ...styles.card, background: "#ef444410", borderColor: "#ef444430", color: "#ef4444", display: "flex", gap: "0.6rem", alignItems: "center" }}>
          <X size={18} /> {error}
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: "4rem" }}>
          <div style={{ width: 36, height: 36, border: "3px solid #3b82f6", borderTopColor: "transparent", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto" }}></div>
        </div>
      )}

      {data && !loading && (
        <div style={{ animation: "fadeIn 0.4s ease-out" }}>
          {/* Fund Info Card - 80/20 Two-Column Layout */}
          <div style={{ ...styles.card, background: "linear-gradient(135deg, #18181b 0%, #121216 100%)", padding: "0.5rem 1.1rem" }}>
            <div style={{ display: "flex", width: "100%", alignItems: "center", gap: "0.5rem" }}>
              {/* Left Column */}
              <div style={{ flex: 1, minWidth: 0, textAlign: "left" }}>
                <a
                  href={`https://fund.eastmoney.com/${data.fund_code}.html`}
                  target="_blank"
                  style={{
                    textDecoration: "none",
                    color: "#3b82f6",
                    fontSize: "1.1rem",
                    fontWeight: 800,
                    letterSpacing: "-0.01em",
                    display: "inline",
                    lineHeight: 1.2
                  }}
                >
                  {data.fund_name || "未知基金"}
                  <ExternalLink
                    size={14}
                    color="currentColor"
                    style={{
                      display: "inline-block",
                      verticalAlign: "middle",
                      marginLeft: "4px",
                      opacity: 0.8,
                      position: "relative",
                      top: "-1px"
                    }}
                  />
                </a>
                {/* Row 2: code + star */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginTop: "0.3rem" }}>
                  <span style={{ color: "#71717a", fontWeight: 600, fontSize: "1.05rem" }}>{data.fund_code}</span>
                  <div
                    onClick={() => toggleWatchlist({ code: data.fund_code, name: data.fund_name || "未知基金" })}
                    style={{ cursor: "pointer", display: "flex", alignItems: "center" }}
                  >
                    {watchlist.find(w => w.code === data.fund_code) ? <Star size={20} fill="#f59e0b" color="#f59e0b" /> : <Star size={20} color="#3f3f46" />}
                  </div>
                </div>
                {/* Row 3: AI button on its own line */}
                <div style={{ marginTop: "0.4rem" }}>
                  <button
                    style={styles.aiBtn}
                    onClick={() => setShowAiTeaser(v => !v)}
                  >
                    ✨ AI 深度诊断
                  </button>
                </div>
              </div>

              {/* Right Column: % number, fixed width, won't shrink */}
              <div style={{ flexShrink: 0, textAlign: "right" }}>
                <div style={{
                  fontSize: "1.85rem",
                  fontWeight: 900,
                  color: (data.estimated_change || 0) >= 0 ? "#ef4444" : "#10b981",
                  letterSpacing: "-0.02em",
                  whiteSpace: "nowrap" as const,
                }}>
                  {data.estimated_change != null ? (data.estimated_change >= 0 ? "+" : "-") : ""}
                  {data.estimated_change != null ? Math.abs(data.estimated_change).toFixed(2) : "0.00"}%
                </div>
              </div>
            </div>
          </div>

          {/* AI Teaser Panel */}
          {showAiTeaser && (
            <div style={styles.aiPanel}>
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", color: "#a78bfa", fontWeight: 800, fontSize: "1rem" }}>
                  <ShieldCheck size={20} /> AI 深度诊断报告
                </div>
                <span style={{
                  fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.05em",
                  color: "#fbbf24", background: "rgba(251,191,36,0.12)",
                  border: "1px solid rgba(251,191,36,0.3)",
                  padding: "0.2rem 0.6rem", borderRadius: "2rem",
                }}>
                  即将上线
                </span>
              </div>

              {/* Feature pills */}
              <div style={{ display: "flex", flexWrap: "wrap" as const, gap: "0.4rem", marginBottom: "1.1rem" }}>
                {["持仓风格诊断", "行业赛道解读", "风险等级评级", "买卖信号参考"].map(f => (
                  <span key={f} style={{
                    fontSize: "0.78rem", fontWeight: 600,
                    color: "#c4b5fd", background: "rgba(139,92,246,0.12)",
                    border: "1px solid rgba(139,92,246,0.25)",
                    padding: "0.2rem 0.65rem", borderRadius: "2rem",
                  }}>✦ {f}</span>
                ))}
              </div>

              {/* Blurred mock content */}
              <div style={{ position: "relative" as const, marginBottom: "1.1rem", userSelect: "none" as const }}>
                <div style={{ filter: "blur(5px)", pointerEvents: "none" as const, opacity: 0.6 }}>
                  <div style={{ height: "0.85rem", background: "#3f3f46", borderRadius: "4px", marginBottom: "0.55rem", width: "92%" }} />
                  <div style={{ height: "0.85rem", background: "#3f3f46", borderRadius: "4px", marginBottom: "0.55rem", width: "78%" }} />
                  <div style={{ height: "0.85rem", background: "#3f3f46", borderRadius: "4px", marginBottom: "0.55rem", width: "85%" }} />
                  <div style={{ height: "0.85rem", background: "#3f3f46", borderRadius: "4px", width: "60%" }} />
                </div>
                <div style={{
                  position: "absolute" as const, inset: 0,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: "1.5rem",
                }}>
                  🔒
                </div>
              </div>

              {/* Price */}
              <div style={{
                background: "linear-gradient(135deg, rgba(251,191,36,0.08) 0%, rgba(139,92,246,0.08) 100%)",
                border: "1px solid rgba(251,191,36,0.25)",
                borderRadius: "0.75rem",
                padding: "0.65rem 1rem",
                marginBottom: "0.9rem",
                display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem",
              }}>
                <div style={{ fontSize: "1.3rem", fontWeight: 900, color: "#fbbf24", letterSpacing: "-0.02em", whiteSpace: "nowrap" as const }}>
                  ¥19 <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#a1a1aa" }}>/ 年</span>
                </div>
                <span style={{
                  fontSize: "0.72rem", fontWeight: 700,
                  color: "#f87171", background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.25)",
                  padding: "0.25rem 0.6rem", borderRadius: "2rem", whiteSpace: "nowrap" as const,
                }}>
                  早鸟价 · 限前 100 名
                </span>
              </div>

              {/* CTA */}
              <a
                href="https://wj.qq.com/s2/26732651/2402/"
                target="_blank"
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center", gap: "0.5rem",
                  padding: "0.65rem 1rem",
                  borderRadius: "0.75rem",
                  background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)",
                  color: "#fff", fontSize: "0.9rem", fontWeight: 700,
                  textDecoration: "none",
                  boxShadow: "0 0 20px rgba(139,92,246,0.3)",
                }}
              >
                加入等待名单 →
              </a>
            </div>
          )}

          {/* Table Card */}
          <div style={{ ...styles.card, padding: "0.25rem 0.5rem" }}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={{ ...styles.th, width: "auto" }}>重仓股票</th>
                  <th style={{ ...styles.th, textAlign: "right", width: "50px" }}>占比</th>
                  <th style={{ ...styles.th, textAlign: "right", width: "50px" }}>涨跌</th>
                  <th style={{ ...styles.th, textAlign: "right", width: "50px" }}>贡献</th>
                </tr>
              </thead>
              <tbody>
                {data.holdings.map((h) => (
                  <tr key={h.code}>
                    <td style={styles.td}>
                      <div style={{ display: "flex", alignItems: "baseline", gap: "0.3rem" }}>
                        <span style={{ fontWeight: 600, color: "#e4e4e7", whiteSpace: "nowrap" }}>{h.name}</span>
                        <span style={{ fontSize: "0.75rem", color: "#52525b", fontWeight: 500 }}>{h.code}</span>
                      </div>
                    </td>
                    <td style={{ ...styles.td, textAlign: "right", color: "#a1a1aa", fontWeight: 500 }}>{h.weight_pct}%</td>
                    <td style={{ 
                      ...styles.td, textAlign: "right", 
                      color: (h.change_pct || 0) >= 0 ? "#f87171" : "#34d399",
                      fontWeight: 700
                    }}>
                      {h.change_pct != null ? (h.change_pct >= 0 ? `+${h.change_pct.toFixed(2)}` : h.change_pct.toFixed(2)) : "—"}%
                    </td>
                    <td style={{ 
                      ...styles.td, textAlign: "right", 
                      color: (h.contribution || 0) >= 0 ? "#f87171" : "#34d399",
                      fontSize: "0.9rem",
                      fontWeight: 600
                    }}>
                      {h.contribution != null ? (h.contribution >= 0 ? `+${h.contribution.toFixed(2)}` : h.contribution.toFixed(2)) : "—"}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Compliance Disclaimer */}
      <footer style={styles.footer}>
        <div style={styles.mvpBanner}>
          <div style={styles.mvpBannerTitle}>
            <Info size={18} /> 重要提示
          </div>
          <div style={styles.mvpBannerText}>
            本产品持续迭代优化，致力于为您提供专业、精准的基金分析体验。
            如需进一步了解或获取定制化服务，欢迎联系我们
            {SALES_EMAIL ? (
              <>
                ：{" "}
                <a style={styles.mvpBannerLink} href={`mailto:${SALES_EMAIL}`}>
                  {SALES_EMAIL}
                </a>
                {" "}
                <Copy
                  size={11}
                  style={{ cursor: "pointer", display: "inline-block", verticalAlign: "middle", marginLeft: "2px", color: "#3b82f6" }}
                  onClick={() => { navigator.clipboard.writeText(SALES_EMAIL); showBubble("邮箱已复制"); }}
                />
              </>
            ) : (
              "。"
            )}
          </div>
        </div>

        <div style={{ color: "#52525b", fontSize: "0.75rem", marginBottom: "0.5rem", fontWeight: 600, letterSpacing: "0.04em", textTransform: "uppercase" as const }}>
          合规提示与风险声明
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem", fontSize: "0.8rem" }}>
          <p style={{ margin: 0 }}>1. <strong>非官方数据</strong>：本工具仅根据基金季度报告披露的重仓股及实时行情进行数学估算，不代表基金真实净值，不构成投资建议。</p>
          <p style={{ margin: 0 }}>2. <strong>局限性说明</strong>：估算未考虑重仓股以外的持仓、现金比例、调仓变动及管理成本。请以官方每日发布的净值为准。</p>
          <p style={{ margin: 0 }}>3. <strong>风险提示</strong>：市场有风险，投资需谨慎。本程序不对任何投资损益负责。</p>
        </div>
        <div style={{ marginTop: "1rem", textAlign: "center" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" as const, justifyContent: "center" }}>
            <a href="https://github.com/akfamily/akshare" target="_blank" style={{ color: "#3b82f6", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.4rem", fontWeight: 600 }}>
              Data by AkShare <ExternalLink size={14} />
            </a>
            <span style={{ color: "#3f3f46" }}>·</span>
            <a href="https://finance.sina.com.cn" target="_blank" style={{ color: "#3b82f6", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.4rem", fontWeight: 600 }}>
              新浪财经 <ExternalLink size={14} />
            </a>
          </span>
        </div>
      </footer>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translate(-50%, -20px); }
          15% { opacity: 1; transform: translate(-50%, 0); }
          85% { opacity: 1; transform: translate(-50%, 0); }
          100% { opacity: 0; transform: translate(-50%, -20px); }
        }
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); transform: scale(1); }
          70% { box-shadow: 0 0 0 10px rgba(139, 92, 246, 0); transform: scale(1.02); }
          100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0); transform: scale(1); }
        }
        body { background: #0a0a0c; margin: 0; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
        input::placeholder { color: #3f3f46; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #27272a; borderRadius: 3px; }
      `}} />
    </main>
  );
}
