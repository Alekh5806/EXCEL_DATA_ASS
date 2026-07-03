import React, { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  ChevronDown,
  ChevronRight,
  Database,
  Download,
  FileUp,
  Loader2,
  RefreshCw,
  Send,
  User,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

const starterMessages = [
  {
    role: "assistant",
    answer: "Ask a question about your imported Excel process data.",
    sql: "",
    data: [],
    chart: null,
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

  async function sendMessage(event) {
    event.preventDefault();
    const message = input.trim();
    if (!message || isLoading) return;

    setMessages((current) => [...current, { role: "user", answer: message }]);
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
      setMessages((current) => [...current, { role: "assistant", ...data }]);
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
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          answer: `${data.message} Total rows in database: ${data.total_rows}.`,
          sql: "",
          data: [{ source_file: data.source_file, rows_created: data.rows_created }],
          chart: null,
        },
      ]);
    } catch (uploadError) {
      setError(uploadError.message);
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="chat-workspace">
        <header className="topbar">
          <div className="brand-mark" aria-hidden="true">
            <Database size={22} />
          </div>
          <div>
            <h1>Excel Data Intelligence Chatbot</h1>
            <p>Query imported process data with plain English.</p>
          </div>
        </header>

        <form className="upload-panel" onSubmit={uploadExcel}>
          <label className="file-picker">
            <FileUp size={17} />
            <span>{selectedFile ? selectedFile.name : "Choose Excel file"}</span>
            <input
              type="file"
              accept=".xlsx"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            />
          </label>
          <label className="replace-toggle">
            <input
              type="checkbox"
              checked={replaceSource}
              onChange={(event) => setReplaceSource(event.target.checked)}
            />
            <span>Re-import same file</span>
          </label>
          <button type="submit" disabled={!selectedFile || isUploading}>
            {isUploading ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />}
            <span>Import</span>
          </button>
          {uploadStatus && <span className="upload-status">{uploadStatus}</span>}
        </form>

        <section className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <ChatMessage key={`${message.role}-${index}`} message={message} />
          ))}
          {isLoading && <LoadingMessage />}
        </section>

        {error && <div className="error-banner">{error}</div>}

        <form className="composer" onSubmit={sendMessage}>
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Ask about max, min, average, count, or a date..."
            aria-label="Chat message"
          />
          <button type="submit" disabled={isLoading || !input.trim()} aria-label="Send message">
            {isLoading ? <Loader2 className="spin" size={19} /> : <Send size={19} />}
          </button>
        </form>
      </section>
    </main>
  );
}

function ChatMessage({ message }) {
  const isUser = message.role === "user";

  return (
    <article className={`message-row ${isUser ? "user-row" : "assistant-row"}`}>
      <div className="avatar" aria-hidden="true">
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>
      <div className="message-bubble">
        <div className="message-heading">
          <p>{message.answer}</p>
          {!isUser && (
            <button
              className="export-button"
              type="button"
              onClick={() => downloadReport(message)}
              aria-label="Export answer report"
            >
              <Download size={16} />
            </button>
          )}
        </div>
        {!isUser && <ResultDetails sql={message.sql} data={message.data} chart={message.chart} />}
      </div>
    </article>
  );
}

function ResultDetails({ sql, data, chart }) {
  const [showSql, setShowSql] = useState(false);
  const [showData, setShowData] = useState(false);
  const hasSql = Boolean(sql);
  const hasData = Array.isArray(data) && data.length > 0;
  const hasChart = Boolean(chart?.data?.length);

  if (!hasSql && !hasData && !hasChart) return null;

  return (
    <div className="result-details">
      {hasChart && <TrendChart chart={chart} />}
      {hasSql && (
        <Disclosure label="SQL" isOpen={showSql} onToggle={() => setShowSql((value) => !value)}>
          <pre>{sql}</pre>
        </Disclosure>
      )}
      {hasData && (
        <Disclosure label="Result" isOpen={showData} onToggle={() => setShowData((value) => !value)}>
          <ResultTable data={data} />
        </Disclosure>
      )}
    </div>
  );
}

function TrendChart({ chart }) {
  return (
    <div className="chart-panel">
      <div className="chart-title">{chart.title}</div>
      <div className="chart-frame">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chart.data} margin={{ top: 10, right: 18, bottom: 4, left: 0 }}>
            <CartesianGrid stroke="#e2e8e3" strokeDasharray="3 3" />
            <XAxis dataKey={chart.xKey} tick={{ fontSize: 12 }} minTickGap={22} />
            <YAxis tick={{ fontSize: 12 }} width={54} />
            <Tooltip formatter={(value) => formatCell(value)} labelFormatter={(label) => `Time: ${label}`} />
            <Line
              type="monotone"
              dataKey={chart.yKey}
              stroke="#2d5c70"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Disclosure({ label, isOpen, onToggle, children }) {
  return (
    <div className="disclosure">
      <button type="button" onClick={onToggle}>
        {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span>{label}</span>
      </button>
      {isOpen && <div className="disclosure-body">{children}</div>}
    </div>
  );
}

function ResultTable({ data }) {
  const columns = useMemo(() => Object.keys(data[0] || {}), [data]);

  return (
    <div className="table-scroll">
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
    <article className="message-row assistant-row">
      <div className="avatar" aria-hidden="true">
        <Bot size={18} />
      </div>
      <div className="message-bubble loading">
        <Loader2 className="spin" size={18} />
        <span>Thinking</span>
      </div>
    </article>
  );
}

function formatCell(value) {
  if (value === null || value === undefined) return "missing";
  if (typeof value === "number") return Number.isInteger(value) ? value : value.toFixed(4);
  return String(value);
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
