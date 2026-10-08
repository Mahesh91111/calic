import { useCallback, useEffect, useState } from "react";
import {
  calculate,
  clearHistory,
  deleteHistoryItem,
  getHistory,
} from "./api";

// label shown on the key, value inserted into the expression, css class
const SCI_KEYS = [
  ["sin", "sin(", "fn"],
  ["cos", "cos(", "fn"],
  ["tan", "tan(", "fn"],
  ["log", "log(", "fn"],
  ["ln", "ln(", "fn"],
  ["√", "sqrt(", "fn"],
  ["x²", "^2", "fn"],
  ["xʸ", "^", "fn"],
  ["n!", "!", "fn"],
  ["π", "π", "fn"],
  ["e", "e", "fn"],
  ["1/x", "1/(", "fn"],
];

const MAIN_KEYS = [
  ["AC", "AC", "danger"],
  ["(", "(", "op"],
  [")", ")", "op"],
  ["÷", "÷", "op"],
  ["7", "7", "num"],
  ["8", "8", "num"],
  ["9", "9", "num"],
  ["×", "×", "op"],
  ["4", "4", "num"],
  ["5", "5", "num"],
  ["6", "6", "num"],
  ["−", "-", "op"],
  ["1", "1", "num"],
  ["2", "2", "num"],
  ["3", "3", "num"],
  ["+", "+", "op"],
  ["±", "NEG", "num"],
  ["0", "0", "num"],
  [".", ".", "num"],
  ["=", "=", "equals"],
];

const OPERATORS = ["+", "-", "×", "÷", "^"];

export default function App() {
  const [expression, setExpression] = useState("");
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [mode, setMode] = useState("deg");
  const [history, setHistory] = useState([]);
  const [finished, setFinished] = useState(false); // true right after "="
  const [loading, setLoading] = useState(false);
  const [serverDown, setServerDown] = useState(false);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getHistory());
      setServerDown(false);
    } catch {
      setServerDown(true);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const insert = useCallback(
    (token) => {
      setError("");
      const isOperator = OPERATORS.includes(token) || token === "!";
      if (finished) {
        setFinished(false);
        if (isOperator && result) {
          // continue calculating from the previous result
          setExpression(result + token);
        } else {
          setExpression(token);
        }
        setResult("");
        return;
      }
      setExpression((prev) => {
        // avoid two decimal points in one number
        if (token === ".") {
          const lastNumber = prev.split(/[^0-9.]/).pop();
          if (lastNumber.includes(".")) return prev;
          if (lastNumber === "") return prev + "0.";
        }
        // replace a trailing operator with the new one
        if (OPERATORS.includes(token) && token !== "-") {
          if (prev === "") return prev;
          if (OPERATORS.includes(prev.slice(-1))) return prev.slice(0, -1) + token;
        }
        return prev + token;
      });
    },
    [finished, result]
  );

  const backspace = useCallback(() => {
    setError("");
    if (finished) {
      setFinished(false);
      setResult("");
      return;
    }
    setExpression((prev) => prev.replace(/(sqrt\(|sin\(|cos\(|tan\(|log\(|ln\(|.)$/, ""));
  }, [finished]);

  const clearAll = useCallback(() => {
    setExpression("");
    setResult("");
    setError("");
    setFinished(false);
  }, []);

  const toggleSign = useCallback(() => {
    if (finished && result) {
      const flipped = result.startsWith("-") ? result.slice(1) : "-" + result;
      setResult(flipped);
      setExpression(flipped);
      setFinished(false);
      return;
    }
    setExpression((prev) => {
      const negWrapped = prev.match(/\(-(\d+\.?\d*)\)$/);
      if (negWrapped) return prev.slice(0, negWrapped.index) + negWrapped[1];
      const num = prev.match(/(\d+\.?\d*)$/);
      if (num) return prev.slice(0, num.index) + `(-${num[1]})`;
      return prev + "(-";
    });
  }, [finished, result]);

  const equals = useCallback(async () => {
    if (!expression || loading) return;
    // auto-close open brackets like a real calculator
    const open = (expression.match(/\(/g) || []).length;
    const close = (expression.match(/\)/g) || []).length;
    const expr = expression + ")".repeat(Math.max(0, open - close));
    setLoading(true);
    try {
      const data = await calculate(expr, mode);
      setExpression(expr);
      setResult(data.result);
      setError("");
      setFinished(true);
      setServerDown(false);
      loadHistory();
    } catch (err) {
      if (err instanceof TypeError) {
        setServerDown(true);
        setError("Cannot reach server");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [expression, mode, loading, loadHistory]);

  const press = useCallback(
    (value) => {
      if (value === "AC") return clearAll();
      if (value === "=") return equals();
      if (value === "NEG") return toggleSign();
      insert(value);
    },
    [clearAll, equals, toggleSign, insert]
  );

  // keyboard support
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key;
      if (/^[0-9.]$/.test(k)) insert(k);
      else if (k === "+" || k === "-") insert(k);
      else if (k === "*" || k === "x") insert("×");
      else if (k === "/") {
        e.preventDefault();
        insert("÷");
      } else if (k === "^") insert("^");
      else if (k === "%") insert("%");
      else if (k === "!") insert("!");
      else if (k === "(" || k === ")") insert(k);
      else if (k === "Enter" || k === "=") {
        e.preventDefault();
        equals();
      } else if (k === "Backspace") backspace();
      else if (k === "Escape" || k === "Delete") clearAll();
      else return;
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [insert, equals, backspace, clearAll]);

  const removeItem = async (id) => {
    try {
      await deleteHistoryItem(id);
      setHistory((h) => h.filter((i) => i.id !== id));
    } catch {
      loadHistory();
    }
  };

  const clearAllHistory = async () => {
    try {
      await clearHistory();
      setHistory([]);
    } catch {
      loadHistory();
    }
  };

  const reuse = (item) => {
    setExpression(item.expression);
    setResult(item.result);
    setError("");
    setFinished(false);
  };

  return (
    <div className="app">
      <div className="calc">
        <div className="calc-top">
          <h1>Calculator</h1>
          <button
            className="mode"
            onClick={() => setMode((m) => (m === "deg" ? "rad" : "deg"))}
            title="Toggle angle mode"
          >
            {mode.toUpperCase()}
          </button>
        </div>

        <div className="display">
          <div className="expr">{expression || "0"}</div>
          <div className={`res ${error ? "err" : ""}`}>
            {error || (loading ? "…" : result)}
          </div>
        </div>

        <div className="sci">
          {SCI_KEYS.map(([label, value, cls]) => (
            <button key={label} className={`key ${cls}`} onClick={() => press(value)}>
              {label}
            </button>
          ))}
          <button className="key fn" onClick={() => press("%")}>
            %
          </button>
          <button className="key fn" onClick={backspace}>
            ⌫
          </button>
        </div>

        <div className="pad">
          {MAIN_KEYS.map(([label, value, cls]) => (
            <button key={label} className={`key ${cls}`} onClick={() => press(value)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <aside className="history">
        <div className="history-head">
          <h2>History</h2>
          <button className="link" onClick={clearAllHistory} disabled={!history.length}>
            Clear all
          </button>
        </div>

        {serverDown && (
          <div className="banner">
            Backend not reachable. Start it with <code>uvicorn main:app --reload</code>
          </div>
        )}

        {!history.length && !serverDown && (
          <p className="empty">No calculations yet.</p>
        )}

        <ul>
          {history.map((item) => (
            <li key={item.id}>
              <button className="item" onClick={() => reuse(item)} title="Click to reuse">
                <span className="item-expr">{item.expression}</span>
                <span className="item-res">= {item.result}</span>
              </button>
              <button
                className="del"
                onClick={() => removeItem(item.id)}
                aria-label="Delete"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  );
}
