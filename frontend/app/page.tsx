"use client";

import { useState, useEffect, useCallback } from "react";
import { 
  Search, Star, ArrowUpRight, ArrowDownRight, 
  Info, ExternalLink, X, ShieldCheck, Clock
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

type Sentiment = {
  status: string;
  up: number;
  down: number;
  flat: number;
  total: number;
  time: string;
  trading: boolean;
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
    marginBottom: "1.5rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "0.5rem",
    flexWrap: "nowrap" as const, // Never wrap to ensure visibility
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
  },
  footer: {
    marginTop: "2.5rem", // Reduced margin
    paddingTop: "1.5rem",
    borderTop: "1px solid #1a1a20",
    fontSize: "0.8rem",
    color: "#71717a",
    lineHeight: 1.6,
  }
};

// --- Components ---

export default function Home() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ApiResult | null>(null);
  const [sentiment, setSentiment] = useState<Sentiment | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [showSearch, setShowSearch] = useState(false);
  const [watchlist, setWatchlist] = useState<SearchResult[]>([]);
  const [mounted, setMounted] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

  const fetchSentiment = useCallback(async () => {
    try {
      const url = `${API_BASE}/api/sentiment`;
      const res = await fetch(url);
      const json = await res.json();
      setSentiment(json);
      
      // If still loading or status is ok, keep polling
      const nextDelay = json.status === "loading" ? 3000 : 30000;
      setTimeout(fetchSentiment, nextDelay);
    } catch (e) {
      setTimeout(fetchSentiment, 5000);
    }
  }, [API_BASE]);

  // Initial load
  useEffect(() => {
    setMounted(true);
    const saved = localStorage.getItem("fund_watchlist");
    if (saved) {
      try { setWatchlist(JSON.parse(saved)); } catch (e) {}
    }
    // We only call this once, it will recurse via setTimeout
    fetchSentiment();
  }, []); // Only once on mount

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

  const totalSentiment = (sentiment?.up || 0) + (sentiment?.down || 0);
  const upRatio = totalSentiment > 0 ? ((sentiment?.up || 0) / totalSentiment) * 100 : 50;

  const getSmartTimeLabel = () => {
    if (!sentiment || !sentiment.time) return "";
    const [datePart, timePart] = sentiment.time.split(" ");
    const today = new Date().toISOString().split("T")[0];
    const isToday = datePart === today;
    const timeHM = timePart.substring(0, 5);

    if (sentiment.status === "loading") return "加载中";

    if (sentiment.trading) {
      return timeHM;
    } else {
      if (isToday) {
        const hour = parseInt(timePart.split(":")[0]);
        const minute = parseInt(timePart.split(":")[1]);
        const totalMinutes = hour * 60 + minute;

        if (totalMinutes < 570) return "昨日收盘"; 
        if (totalMinutes >= 900) return "已收盘";
        return "午间休市";
      } else {
        const [y, m, d] = datePart.split("-");
        return `${m}-${d} 收盘`;
      }
    }
  };

  return (
    <main style={styles.container}>
      {/* Header */}
      <header style={styles.header}>
        <h1 style={styles.title}>
          <ShieldCheck size={24} color="#3b82f6" />
          基金透视
        </h1>
        
        {sentiment ? (
          sentiment.status === "ok" ? (
            <div style={styles.heatBarContainer}>
              <span style={{ fontSize: "0.75rem", color: "#ef4444", fontWeight: 800 }}>{sentiment.up}</span>
              <div style={styles.heatBar}>
                <div style={{ width: `${upRatio}%`, background: "linear-gradient(90deg, #ef4444, #f87171)" }}></div>
                <div style={{ width: `${100 - upRatio}%`, background: "linear-gradient(90deg, #34d399, #10b981)" }}></div>
              </div>
              <span style={{ fontSize: "0.75rem", color: "#10b981", fontWeight: 800 }}>{sentiment.down}</span>
              <div style={{ width: "1px", height: "12px", background: "#3f3f46", margin: "0 2px" }}></div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.2rem", color: "#71717a", fontSize: "0.7rem", fontWeight: 500 }}>
                <Clock size={12} />
                {getSmartTimeLabel()}
              </div>
            </div>
          ) : (
            <div style={{ ...styles.heatBarContainer, opacity: 0.6 }}>
              <span style={{ fontSize: "0.65rem", color: "#71717a" }}>行情加载中...</span>
            </div>
          )
        ) : (
          <div style={{ ...styles.heatBarContainer, opacity: 0.6 }}>
            <span style={{ fontSize: "0.65rem", color: "#71717a" }}>连接中...</span>
          </div>
        )}
      </header>

      {/* Search */}
      <div style={styles.inputContainer}>
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
          onFocus={() => code.length >= 2 && setShowSearch(true)}
        />
        
        {showSearch && searchResults.length > 0 && (
          <div style={{
            position: "absolute", top: "100%", left: 0, right: 0,
            background: "#18181b", border: "1px solid #27272a", borderRadius: "0.75rem",
            marginTop: "0.5rem", zIndex: 10, maxHeight: "320px", overflowY: "auto",
            boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5)"
          }}>
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
          </div>
        )}
      </div>

      {watchlist.length > 0 && (
        <div style={styles.watchlist}>
          {watchlist.map(f => (
            <div key={f.code} style={styles.watchlistItem} onClick={() => fetchFund(f)}>
              {f.name}
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
            <div style={{ display: "flex", width: "100%", alignItems: "center" }}>
              {/* Left Column: 75% */}
              <div style={{ width: "75%", textAlign: "left" }}>
                <h2 style={{ fontSize: "1.1rem", fontWeight: 800, color: "#fff", letterSpacing: "-0.01em", marginBottom: "0.1rem" }}>
                  {data.fund_name || "华夏成长"}
                </h2>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ color: "#71717a", fontWeight: 600, fontSize: "1.05rem" }}>{data.fund_code}</span>
                  <div 
                    onClick={() => toggleWatchlist({ code: data.fund_code, name: data.fund_name || "华夏成长" })} 
                    style={{ cursor: "pointer", display: "flex", alignItems: "center" }}
                  >
                    {watchlist.find(w => w.code === data.fund_code) ? <Star size={18} fill="#f59e0b" color="#f59e0b" /> : <Star size={18} color="#3f3f46" />}
                  </div>
                </div>
              </div>

              {/* Right Column: 25% */}
              <div style={{ width: "25%", textAlign: "right", display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
                <div style={{ 
                  fontSize: "1.85rem", 
                  fontWeight: 900, 
                  color: (data.estimated_change || 0) >= 0 ? "#ef4444" : "#10b981",
                  display: "flex", alignItems: "center", letterSpacing: "-0.02em"
                }}>
                  {data.estimated_change != null ? (data.estimated_change >= 0 ? "+" : "-") : ""}
                  {data.estimated_change != null ? Math.abs(data.estimated_change).toFixed(2) : "0.00"}%
                </div>
              </div>
            </div>
          </div>

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
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem", color: "#a1a1aa" }}>
          <Info size={18} />
          <strong style={{ fontSize: "0.95rem", letterSpacing: "0.02em" }}>合规提示与风险声明</strong>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.85rem" }}>
          <p style={{ margin: 0 }}>1. <strong>非官方数据</strong>：本工具仅根据基金季度报告披露的十大重仓股及实时行情进行数学估算，不代表基金真实净值，不构成投资建议。</p>
          <p style={{ margin: 0 }}>2. <strong>局限性说明</strong>：估算未考虑重仓股以外的持仓、现金比例、调仓变动及管理成本。请以官方每日发布的净值为准。</p>
          <p style={{ margin: 0 }}>3. <strong>风险提示</strong>：市场有风险，投资需谨慎。本程序不对任何投资损益负责。</p>
        </div>
        <div style={{ marginTop: "2rem", textAlign: "center" }}>
          <a href="https://github.com/akfamily/akshare" target="_blank" style={{ color: "#3b82f6", textDecoration: "none", display: "inline-flex", alignItems: "center", gap: "0.4rem", fontWeight: 600 }}>
            Data by AkShare <ExternalLink size={14} />
          </a>
        </div>
      </footer>

      <style dangerouslySetInnerHTML={{ __html: `
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        body { background: #0a0a0c; margin: 0; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
        input::placeholder { color: #3f3f46; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #27272a; borderRadius: 3px; }
      `}} />
    </main>
  );
}
