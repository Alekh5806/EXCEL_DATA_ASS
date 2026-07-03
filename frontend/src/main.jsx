import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  Bot,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Clock3,
  Copy,
  Database,
  Download,
  FileSpreadsheet,
  FileUp,
  History,
  LayoutDashboard,
  Layers3,
  Loader2,
  MoreHorizontal,
  MessageSquare,
  Moon,
  RefreshCw,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Thermometer,
  UploadCloud,
  User,
  UserCircle2,
  X,
} from "lucide-react";
import {
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const FALLBACK_DISTRIBUTION_DATA = [
  { name: "Numeric", value: 9, color: "#7c4dff" },
  { name: "Text", value: 2, color: "#06b6d4" },
  { name: "Date/Time", value: 4, color: "#3b82f6" },
  { name: "Audit", value: 1, color: "#8b5cf6" },
];
const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "overview", label: "Data Overview", icon: LayoutDashboard },
  { id: "insights", label: "Insights", icon: Sparkles },
  { id: "history", label: "History", icon: History },
  { id: "settings", label: "Settings", icon: Settings },
];

const starterMessages = [
  {
    role: "assistant",
    answer: "Hello! Ask me anything about your imported Excel process data.",
    sql: "",
    data: [],
    chart: null,
    timestamp: formatClock(new Date()),
  },
];

function App() {
  const [messages, setMessages] = useState(starterMessages);
  const [input, setInput] = useState("What was the highest temperature on April 8?");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [replaceSource, setReplaceSource] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [activeView, setActiveView] = useState("chat");
  const [theme, setTheme] = useState("dark");
  const [dashboardOverview, setDashboardOverview] = useState(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(true);
  const [isFilesDrawerOpen, setIsFilesDrawerOpen] = useState(false);
  const [importMeta, setImportMeta] = useState({
    fileName: "No file imported yet",
    fileSize: 0,
    totalRows: 0,
    dateRange: "No dates available",
    importedAt: "No imports yet",
  });

  const deferredInput = input;

  useEffect(() => {
    loadDashboardSummary();
  }, []);

  const overview = useMemo(() => {
    const sourceFileCount = dashboardOverview?.source_file_count ?? 0;
    const totalRows = dashboardOverview?.total_rows ?? importMeta.totalRows;
    const totalColumns = dashboardOverview?.total_columns ?? 16;
    const distribution = dashboardOverview?.column_distribution?.length
      ? dashboardOverview.column_distribution
      : FALLBACK_DISTRIBUTION_DATA;
    const insights = dashboardOverview?.insights || {};

    return {
      totalRows,
      totalColumns,
      dateRange: dashboardOverview?.date_range?.label || importMeta.dateRange,
      latestLoadedDate: dashboardOverview?.latest_imported_at ? formatDateTimeCompact(dashboardOverview.latest_imported_at) : importMeta.importedAt,
      sourceFileCount,
      sourceFiles: dashboardOverview?.source_files || [],
      distribution,
      topCards: [
        {
          title: "Total Rows",
          value: new Intl.NumberFormat().format(totalRows ?? 0),
          subtitle: "Imported records",
          icon: Database,
          tone: "purple",
        },
        {
          title: "Total Columns",
          value: totalColumns,
          subtitle: "Queryable fields",
          icon: LayoutDashboard,
          tone: "blue",
        },
        {
          title: "Date Range",
          value: dashboardOverview?.date_range?.label || importMeta.dateRange,
          subtitle: "Available dates",
          icon: CalendarDays,
          tone: "cyan",
        },
        {
          title: "Last Data Loaded",
          value: dashboardOverview?.latest_imported_at ? formatDateTimeCompact(dashboardOverview.latest_imported_at) : "No imports yet",
          subtitle: sourceFileCount ? `View ${sourceFileCount} distinct file(s)` : "No imported files yet",
          icon: Clock3,
          tone: "pink",
          onClick: sourceFileCount ? () => setIsFilesDrawerOpen(true) : undefined,
        },
      ],
      insights: [
        {
          title: "Highest Biomass Temp",
          value: formatInsightValue(insights.highest_biomass_temperature),
          subtitle: "Maximum value in database",
          icon: Thermometer,
          tone: "purple",
        },
        {
          title: "Avg Reactor Flow",
          value: formatInsightValue(insights.avg_reactor_flow),
          subtitle: "Database average across imported rows",
          icon: Activity,
          tone: "blue",
        },
        {
          title: "Distinct Stages",
          value: new Intl.NumberFormat().format(insights.distinct_stages ?? 0),
          subtitle: "Unique process stages in database",
          icon: Layers3,
          tone: "cyan",
        },
        {
          title: "Data Quality Score",
          value: formatPercentage(insights.data_quality_score),
          subtitle: "Computed from non-empty database fields",
          icon: ShieldCheck,
          tone: "orange",
        },
      ],
    };
  }, [dashboardOverview, importMeta]);

  async function loadDashboardSummary(fileSizeOverride) {
    setIsDashboardLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/summary/`);

      if (!response.ok) {
        throw new Error(`Dashboard summary failed with status ${response.status}`);
      }

      const payload = await response.json();
      const nextOverview = payload.overview || null;

      setDashboardOverview(nextOverview);
      setImportMeta((current) => ({
        ...current,
        fileName: nextOverview?.latest_source_file || current.fileName,
        fileSize: fileSizeOverride ?? current.fileSize,
        totalRows: nextOverview?.total_rows ?? 0,
        dateRange: nextOverview?.date_range?.label || "No dates available",
        importedAt: nextOverview?.latest_imported_at ? formatDateTime(nextOverview.latest_imported_at) : current.importedAt,
      }));
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setIsDashboardLoading(false);
    }
  }

  async function sendMessage(event) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isLoading) return;

    setMessages((current) => [...current, { role: "user", answer: message, timestamp: formatClock(new Date()) }]);
    setInput("");
    setError("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      setMessages((current) => [...current, { role: "assistant", timestamp: formatClock(new Date()), ...data }]);
    } catch (requestError) {
      setError(requestError.message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          answer: "I could not reach the backend API. Check that Django is running and the API URL is correct.",
          sql: "",
          data: [],
          chart: null,
          timestamp: formatClock(new Date()),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function uploadExcel(event) {
    event.preventDefault();
    if (!selectedFile || isUploading) return;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("replace_source", String(replaceSource));

    setIsUploading(true);
    setUploadStatus("");
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/upload/`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `Upload failed with status ${response.status}`);
      }

      setUploadStatus(data.message);
      setImportMeta((current) => ({
        ...current,
        fileName: data.source_file,
        fileSize: selectedFile?.size || current.fileSize,
        totalRows: data.total_rows,
        importedAt: formatClock(new Date()),
      }));
      await loadDashboardSummary(selectedFile?.size || importMeta.fileSize);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          answer: `${data.message} Total rows in database: ${data.total_rows}.`,
          sql: "",
          data: [{ source_file: data.source_file, rows_created: data.rows_created }],
          chart: null,
          timestamp: formatClock(new Date()),
        },
      ]);
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setIsUploading(false);
    }
  }

  const pageTitle = NAV_ITEMS.find((item) => item.id === activeView)?.label || "Chat";

  return (
    <main className={`app-shell theme-${theme}`}>
      <div className="ambient ambient-one" aria-hidden="true" />
      <div className="ambient ambient-two" aria-hidden="true" />
      <div className="layout-shell">
        <Sidebar
          activeView={activeView}
          onNavigate={setActiveView}
          theme={theme}
          onToggleTheme={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
        />

        <section className="workspace-shell">
          <HeaderCard title={pageTitle} />

          {activeView === "chat" ? (
            <>
              <UploadCard
                selectedFile={selectedFile}
                replaceSource={replaceSource}
                setReplaceSource={setReplaceSource}
                isUploading={isUploading}
                onUpload={uploadExcel}
                onSelectFile={setSelectedFile}
                uploadStatus={uploadStatus}
                importMeta={importMeta}
              />

              <section className="messages-shell" aria-live="polite">
                <div className="messages-scroll">
                  <AnimatePresence initial={false}>
                    {messages.map((message, index) => (
                      <ChatMessage key={`${message.role}-${index}-${message.timestamp}`} message={message} theme={theme} />
                    ))}
                    {isLoading && <LoadingMessage key="loading-message" />}
                  </AnimatePresence>
                </div>

                {error && <div className="error-banner">{error}</div>}

                <form className="composer-shell" onSubmit={sendMessage}>
                  <div className="composer-pill">
                    <input
                      value={deferredInput}
                      onChange={(event) => setInput(event.target.value)}
                      placeholder="Ask about max, min, average, count, or a date..."
                      aria-label="Chat message"
                    />
                    <motion.button
                      whileHover={{ y: -2, scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      type="submit"
                      disabled={isLoading || !input.trim()}
                      aria-label="Send message"
                    >
                      {isLoading ? <Loader2 className="spin" size={19} /> : <Send size={18} />}
                    </motion.button>
                  </div>
                </form>
              </section>
            </>
          ) : activeView === "overview" ? (
            <>
              <UploadCard
                selectedFile={selectedFile}
                replaceSource={replaceSource}
                setReplaceSource={setReplaceSource}
                isUploading={isUploading}
                onUpload={uploadExcel}
                onSelectFile={setSelectedFile}
                uploadStatus={uploadStatus}
                importMeta={importMeta}
              />
              <DataOverview theme={theme} overview={overview} isLoading={isDashboardLoading} />
            </>
          ) : (
            <PlaceholderView view={activeView} />
          )}
        </section>
      </div>

      <FilesDrawer
        isOpen={isFilesDrawerOpen}
        files={overview.sourceFiles}
        lastLoadedDate={overview.latestLoadedDate}
        onClose={() => setIsFilesDrawerOpen(false)}
      />

      <MobileNav activeView={activeView} onNavigate={setActiveView} />
    </main>
  );
}

function Sidebar({ activeView, onNavigate, theme, onToggleTheme }) {
  return (
    <aside className="sidebar-shell">
      <div className="sidebar-top">
        <div className="brand-shell">
          <div className="sidebar-logo" aria-hidden="true">
            <Database size={22} />
          </div>
          <div className="brand-copy">
            <strong>Excel Data</strong>
            <span>Intelligence</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = item.id === activeView;

            return (
              <motion.button
                key={item.id}
                type="button"
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.97 }}
                className={`sidebar-button ${isActive ? "active" : ""}`}
                onClick={() => onNavigate(item.id)}
                aria-label={item.label}
                title={item.label}
              >
                <Icon size={19} />
                <span>{item.label}</span>
              </motion.button>
            );
          })}
        </nav>
      </div>

      <div className="sidebar-bottom">
        <button type="button" className="theme-toggle-row" onClick={onToggleTheme} aria-label="Toggle theme" title="Toggle theme">
          <div className="theme-toggle-copy">
            {theme === "dark" ? <Moon size={17} /> : <Sun size={17} />}
            <span>{theme === "dark" ? "Dark Mode" : "Light Mode"}</span>
          </div>
          <span className={`theme-switch ${theme === "dark" ? "on" : ""}`} aria-hidden="true">
            <span />
          </span>
        </button>

        <div className="sidebar-profile">
          <div className="sidebar-profile-avatar">
            <UserCircle2 size={24} />
          </div>
          <div className="sidebar-profile-copy">
            <strong>Data Analyst</strong>
            <span>Admin</span>
          </div>
          <ChevronRight size={16} />
        </div>
      </div>
    </aside>
  );
}

function HeaderCard({ title }) {
  return (
    <motion.header
      className="hero-card"
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div>
        <h1>Excel Data Intelligence Chatbot</h1>
        <p>Query imported process data using natural language.</p>
      </div>

      <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }} type="button" className="ghost-gradient-button">
        <History size={16} />
        <span>Import History</span>
      </motion.button>
    </motion.header>
  );
}

function UploadCard({
  selectedFile,
  replaceSource,
  setReplaceSource,
  isUploading,
  onUpload,
  onSelectFile,
  uploadStatus,
  importMeta,
}) {
  const displayName = selectedFile?.name || importMeta.fileName;
  const displaySize = formatFileSize(selectedFile?.size || importMeta.fileSize);

  return (
    <motion.form
      className="upload-card"
      onSubmit={onUpload}
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05, duration: 0.35 }}
    >
      <label className="file-chip">
        <div className="file-chip-icon">
          <FileSpreadsheet size={22} />
        </div>
        <div className="file-chip-copy">
          <strong>{displayName}</strong>
          <span>{displaySize}</span>
        </div>
        <input
          type="file"
          accept=".xlsx"
          onChange={(event) => onSelectFile(event.target.files?.[0] || null)}
        />
      </label>

      <label className="checkbox-row">
        <input
          type="checkbox"
          checked={replaceSource}
          onChange={(event) => setReplaceSource(event.target.checked)}
        />
        <span>Re-import same file</span>
      </label>

      <motion.button whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }} type="submit" className="gradient-button" disabled={!selectedFile || isUploading}>
        {isUploading ? <Loader2 className="spin" size={17} /> : <UploadCloud size={17} />}
        <span>Import</span>
      </motion.button>

      <div className="upload-card-meta">
        <span>{uploadStatus || `Last import: ${importMeta.importedAt}`}</span>
      </div>
    </motion.form>
  );
}

function ChatMessage({ message, theme }) {
  const isUser = message.role === "user";

  return (
    <motion.article
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.26 }}
      className={`message-row ${isUser ? "user-row" : "assistant-row"}`}
    >
      <div className={`message-avatar ${isUser ? "user" : "assistant"}`} aria-hidden="true">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      {isUser ? (
        <div className="user-bubble">
          <span>{message.answer}</span>
          <small>{message.timestamp}</small>
        </div>
      ) : (
        <div className="assistant-card">
          <div className="assistant-card-header">
            <div>
              <strong>AI Answer</strong>
              <small>{message.timestamp}</small>
            </div>
            <button type="button" className="icon-utility" onClick={() => downloadReport(message)} aria-label="Export answer report">
              <Download size={16} />
            </button>
          </div>

          <p className="assistant-answer">{message.answer}</p>

          <ResultDetails sql={message.sql} data={message.data} chart={message.chart} theme={theme} />
        </div>
      )}
    </motion.article>
  );
}

function ResultDetails({ sql, data, chart, theme }) {
  const [showSql, setShowSql] = useState(false);
  const [showData, setShowData] = useState(false);
  const hasSql = Boolean(sql);
  const hasData = Array.isArray(data) && data.length > 0;
  const hasChart = Boolean(chart?.data?.length);

  if (!hasSql && !hasData && !hasChart) return null;

  return (
    <div className="details-stack">
      {hasChart && <TrendChart chart={chart} theme={theme} />}
      {hasSql && (
        <Disclosure
          label="SQL Executed"
          isOpen={showSql}
          onToggle={() => setShowSql((value) => !value)}
          action={
            <CopyButton
              text={sql}
              label="Copy SQL"
              className="icon-utility"
            />
          }
        >
          <SqlViewer sql={sql} />
        </Disclosure>
      )}
      {hasData && (
        <Disclosure
          label="Result"
          isOpen={showData}
          onToggle={() => setShowData((value) => !value)}
          action={<CopyButton text={JSON.stringify(data, null, 2)} label="Copy result" className="icon-utility" />}
        >
          <ResultTable data={data} />
        </Disclosure>
      )}
    </div>
  );
}

function TrendChart({ chart, theme }) {
  const gradientId = `trend-gradient-${chart.yKey || "value"}`;
  const glowId = `trend-glow-${chart.yKey || "value"}`;

  return (
    <motion.div className="chart-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="chart-card-title">{chart.title}</div>
      <div className="chart-card-frame">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart.data} margin={{ top: 10, right: 18, bottom: 4, left: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="55%" stopColor="#3b82f6" />
                <stop offset="100%" stopColor="#00d4ff" />
              </linearGradient>
              <filter id={glowId} x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <CartesianGrid stroke={theme === "dark" ? "rgba(255,255,255,0.08)" : "#e2e8e3"} strokeDasharray="3 3" />
            <XAxis dataKey={chart.xKey} tick={{ fontSize: 12 }} minTickGap={22} />
            <YAxis tick={{ fontSize: 12 }} width={54} />
            <Tooltip formatter={(value) => formatCell(value)} labelFormatter={(label) => `Time: ${label}`} />
            <Line
              type="monotone"
              dataKey={chart.yKey}
              stroke={`url(#${gradientId})`}
              strokeWidth={4}
              dot={false}
              activeDot={{ r: 4 }}
              filter={`url(#${glowId})`}
              isAnimationActive
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}

function Disclosure({ label, isOpen, onToggle, action, children }) {
  return (
    <section className="disclosure-card">
      <div className="disclosure-header-row">
        <button type="button" onClick={onToggle} className="disclosure-trigger">
          {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <span>{label}</span>
        </button>
        {action}
      </div>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            className="disclosure-body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22 }}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}

function SqlViewer({ sql }) {
  return (
    <div className="sql-viewer">
      <div className="sql-status">
        <span className="status-dot" />
        <span>SQL Executed Successfully</span>
      </div>
      <pre>{sql}</pre>
    </div>
  );
}

function ResultTable({ data }) {
  const columns = useMemo(() => Object.keys(data[0] || {}), [data]);

  return (
    <div className="table-shell">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={column}>{formatCell(row[column])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LoadingMessage() {
  return (
    <motion.article initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="message-row assistant-row">
      <div className="message-avatar assistant" aria-hidden="true">
        <Bot size={18} />
      </div>
      <div className="assistant-card loading-card">
        <Loader2 className="spin" size={18} />
        <span>Thinking...</span>
      </div>
    </motion.article>
  );
}

function DataOverview({ overview, isLoading }) {
  const distributionData = overview.distribution?.length ? overview.distribution : FALLBACK_DISTRIBUTION_DATA;

  return (
    <motion.section className="overview-shell" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="overview-grid top-cards">
        {overview.topCards.map((card, index) => (
          <AnalyticsCard
            key={card.title}
            title={card.title}
            value={card.value}
            subtitle={card.subtitle}
            icon={card.icon}
            tone={card.tone}
            delay={index * 0.04}
            onClick={card.onClick}
          />
        ))}
      </div>

      <div className="overview-analytics-grid">
        <motion.section className="overview-card chart-overview" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
          <div className="section-head">
            <div>
              <strong>Column Distribution</strong>
              <span>Quick shape of your imported schema</span>
            </div>
            <button type="button" className="panel-menu-button" aria-label="More options">
              <MoreHorizontal size={16} />
            </button>
          </div>
          <div className="pie-layout">
            <div className="pie-frame">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={distributionData} innerRadius={52} outerRadius={92} dataKey="value" paddingAngle={3}>
                    {distributionData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="legend-list">
              {distributionData.map((entry) => (
                <div key={entry.name} className="legend-item">
                  <span className="legend-color" style={{ background: entry.color }} />
                  <div className="legend-copy">
                    <strong>{entry.name}</strong>
                    <small>{entry.value} columns</small>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.section>

        <motion.section className="overview-card" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <div className="section-head">
            <div>
              <strong>Data Types</strong>
              <span>{isLoading ? "Refreshing database summary" : "Distribution across database schema"}</span>
            </div>
            <button type="button" className="panel-menu-button" aria-label="More options">
              <MoreHorizontal size={16} />
            </button>
          </div>
          <div className="progress-stack">
            {distributionData.map((entry) => (
              <ProgressBar key={entry.name} label={entry.name} value={(entry.value / Math.max(overview.totalColumns || 1, 1)) * 100} tone={entry.color} />
            ))}
          </div>
        </motion.section>
      </div>

      <div className="insight-grid">
        {overview.insights.map((insight, index) => (
          <AnalyticsCard
            key={insight.title}
            title={insight.title}
            value={insight.value}
            subtitle={insight.subtitle}
            icon={insight.icon}
            tone={insight.tone}
            delay={0.08 + index * 0.04}
          />
        ))}
      </div>
    </motion.section>
  );
}

function AnalyticsCard({ title, value, subtitle, icon: Icon = BarChart3, tone = "blue", delay = 0, onClick }) {
  const wavePath = getSparklinePath(tone);

  if (onClick) {
    return (
      <motion.button
        type="button"
        className={`overview-card analytics-card interactive-card tone-${tone}`}
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.28 }}
        whileHover={{ y: -4 }}
        whileTap={{ scale: 0.99 }}
        onClick={onClick}
      >
        <div className="analytics-icon">
          <Icon size={18} />
        </div>
        <div className="analytics-copy">
          <strong>{title}</strong>
          <h3>{value}</h3>
          <span>{subtitle}</span>
        </div>
        <span className="kpi-wave" aria-hidden="true">
          <svg viewBox="0 0 120 34" preserveAspectRatio="none">
            <path d={wavePath} />
          </svg>
        </span>
      </motion.button>
    );
  }

  return (
    <motion.article
      className={`overview-card analytics-card tone-${tone}`}
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.28 }}
      whileHover={{ y: -4 }}
    >
      <div className="analytics-icon">
        <Icon size={18} />
      </div>
      <div className="analytics-copy">
        <strong>{title}</strong>
        <h3>{value}</h3>
        <span>{subtitle}</span>
      </div>
      <span className="kpi-wave" aria-hidden="true">
        <svg viewBox="0 0 120 34" preserveAspectRatio="none">
          <path d={wavePath} />
        </svg>
      </span>
    </motion.article>
  );
}

function getSparklinePath(tone) {
  if (tone === "purple") return "M0,28 C10,30 14,24 21,20 C28,16 35,19 40,24 C45,29 50,30 56,26 C62,22 67,20 74,24 C81,28 87,22 94,16 C101,10 108,13 114,18 C118,20 120,11 120,7";
  if (tone === "blue") return "M0,29 C11,31 18,24 24,21 C31,18 36,19 42,25 C48,31 57,31 64,24 C71,17 79,18 86,24 C93,30 100,27 106,19 C112,11 117,12 120,8";
  if (tone === "cyan") return "M0,30 C9,31 14,26 21,21 C28,16 34,18 41,24 C48,30 54,30 61,25 C68,20 75,21 82,25 C89,29 96,26 103,18 C110,10 116,14 120,8";
  if (tone === "orange") return "M0,29 C11,31 18,27 25,23 C32,19 38,21 45,26 C52,31 58,31 66,25 C74,19 80,20 88,24 C96,28 103,24 110,16 C116,10 119,12 120,9";
  return "M0,29 C10,31 16,26 22,22 C28,18 35,20 42,24 C49,28 57,30 64,25 C71,20 78,21 86,26 C94,31 101,29 108,21 C114,14 118,15 120,10";
}

function FilesDrawer({ isOpen, files, lastLoadedDate, onClose }) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.button
            type="button"
            className="drawer-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            aria-label="Close imported files panel"
          />
          <motion.aside
            className="files-drawer"
            initial={{ x: "100%", opacity: 0.8 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: "100%", opacity: 0.8 }}
            transition={{ type: "spring", stiffness: 280, damping: 28 }}
            aria-label="Imported files"
          >
            <div className="files-drawer-header">
              <div>
                <strong>Imported Files</strong>
                <span>Distinct files currently loaded into the database.</span>
              </div>
              <button type="button" className="icon-utility" onClick={onClose} aria-label="Close imported files drawer">
                <X size={16} />
              </button>
            </div>

            <div className="files-drawer-summary">
              <div>
                <span>Last data loaded</span>
                <strong>{lastLoadedDate || "No imports yet"}</strong>
              </div>
              <div>
                <span>Distinct files</span>
                <strong>{files.length}</strong>
              </div>
            </div>

            <div className="files-list">
              {files.length ? (
                files.map((fileName, index) => (
                  <div key={`${fileName}-${index}`} className="file-list-item">
                    <div className="file-list-icon">
                      <FileSpreadsheet size={17} />
                    </div>
                    <div className="file-list-copy">
                      <strong>{fileName}</strong>
                      <span>Imported source #{index + 1}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="files-empty-state">
                  <FileSpreadsheet size={18} />
                  <span>No imported files found.</span>
                </div>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function ProgressBar({ label, value, tone }) {
  return (
    <div className="progress-row">
      <div className="progress-meta">
        <strong>{label}</strong>
        <span>{Math.round(value)}%</span>
      </div>
      <div className="progress-track">
        <motion.div className="progress-fill" initial={{ width: 0 }} animate={{ width: `${value}%` }} />
      </div>
    </div>
  );
}

function PlaceholderView({ view }) {
  const copy = {
    insights: "Saved AI highlights and recommended questions will appear here.",
    history: "Import runs and chat sessions will be organized in this history view.",
    settings: "Theme, provider, and model settings can live in this workspace.",
  };

  return (
    <motion.section className="placeholder-card" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <Sparkles size={20} />
      <strong>{NAV_ITEMS.find((item) => item.id === view)?.label}</strong>
      <p>{copy[view] || "This area is reserved for a future workspace module."}</p>
    </motion.section>
  );
}

function MobileNav({ activeView, onNavigate }) {
  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      {NAV_ITEMS.slice(0, 4).map((item) => {
        const Icon = item.icon;
        return (
          <button key={item.id} type="button" className={activeView === item.id ? "active" : ""} onClick={() => onNavigate(item.id)}>
            <Icon size={18} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function CopyButton({ text, label, className }) {
  const [copied, setCopied] = useState(false);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button type="button" className={className} onClick={onCopy} aria-label={label} title={label}>
      {copied ? <Clock3 size={15} /> : <Copy size={15} />}
    </button>
  );
}

function formatCell(value) {
  if (value === null || value === undefined) return "missing";
  if (typeof value === "number") return Number.isInteger(value) ? value : value.toFixed(4);
  return String(value);
}

function formatClock(date) {
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatFileSize(bytes) {
  if (!bytes) return "Unknown size";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatInsightValue(value) {
  if (value === null || value === undefined || value === "") return "No data";
  if (typeof value !== "number") return value;
  return Number.isInteger(value) ? new Intl.NumberFormat().format(value) : value.toFixed(4);
}

function formatPercentage(value) {
  if (typeof value !== "number") return "No data";
  return `${value.toFixed(1)}%`;
}

function formatDateTime(value) {
  const parsedValue = new Date(value);
  if (Number.isNaN(parsedValue.getTime())) return "Unknown import time";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(parsedValue);
}

function formatDateTimeCompact(value) {
  const parsedValue = new Date(value);
  if (Number.isNaN(parsedValue.getTime())) return "Unknown import time";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(parsedValue);
}

function downloadReport(message) {
  const report = [
    "Excel Data Intelligence Chatbot Report",
    "",
    `Answer: ${message.answer || ""}`,
    "",
    message.sql ? `SQL:\n${message.sql}\n` : "",
    message.data?.length ? `Data:\n${JSON.stringify(message.data, null, 2)}\n` : "",
    message.chart ? `Chart:\n${JSON.stringify(message.chart, null, 2)}\n` : "",
  ]
    .filter(Boolean)
    .join("\n");

  const blob = new Blob([report], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "excel-data-chatbot-report.txt";
  link.click();
  URL.revokeObjectURL(url);
}

createRoot(document.getElementById("root")).render(<App />);
