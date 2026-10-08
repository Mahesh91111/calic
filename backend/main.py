"""
Calculator API - FastAPI + SQLite

Endpoints
---------
POST   /api/calculate        evaluate an expression and save it to history
GET    /api/history          list previous calculations (newest first)
DELETE /api/history/{id}     delete one history item
DELETE /api/history          clear all history
GET    /api/health           health check
"""

import ast
import math
import operator
import re
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DB_PATH = Path(__file__).parent / "history.db"

# --------------------------------------------------------------------------
# Database (history storage)
# --------------------------------------------------------------------------


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                expression TEXT NOT NULL,
                result     TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


# --------------------------------------------------------------------------
# Safe expression evaluator
# --------------------------------------------------------------------------

MAX_EXPR_LEN = 200
MAX_POWER = 10_000

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}

CONSTANTS = {"pi": math.pi, "e": math.e}


class CalcError(Exception):
    pass


def _factorial(x: float) -> float:
    if x < 0 or int(x) != x:
        raise CalcError("Factorial needs a non-negative integer")
    if x > 170:
        raise CalcError("Number too large")
    return float(math.factorial(int(x)))


def build_functions(mode: str) -> dict:
    """Trig functions respect DEG / RAD mode."""
    to_rad = (lambda v: math.radians(v)) if mode == "deg" else (lambda v: v)
    from_rad = (lambda v: math.degrees(v)) if mode == "deg" else (lambda v: v)

    def tan(v):
        r = to_rad(v)
        if abs(math.cos(r)) < 1e-12:
            raise CalcError("tan undefined")
        return math.tan(r)

    def log10(v):
        if v <= 0:
            raise CalcError("log needs a positive number")
        return math.log10(v)

    def ln(v):
        if v <= 0:
            raise CalcError("ln needs a positive number")
        return math.log(v)

    def sqrt(v):
        if v < 0:
            raise CalcError("sqrt of a negative number")
        return math.sqrt(v)

    def asin(v):
        if not -1 <= v <= 1:
            raise CalcError("asin domain is -1 to 1")
        return from_rad(math.asin(v))

    def acos(v):
        if not -1 <= v <= 1:
            raise CalcError("acos domain is -1 to 1")
        return from_rad(math.acos(v))

    return {
        "sin": lambda v: math.sin(to_rad(v)),
        "cos": lambda v: math.cos(to_rad(v)),
        "tan": tan,
        "asin": asin,
        "acos": acos,
        "atan": lambda v: from_rad(math.atan(v)),
        "log": log10,
        "ln": ln,
        "sqrt": sqrt,
        "cbrt": lambda v: math.copysign(abs(v) ** (1 / 3), v),
        "abs": abs,
        "exp": math.exp,
        "fact": _factorial,
    }


def evaluate(expression: str, mode: str = "deg") -> float:
    if len(expression) > MAX_EXPR_LEN:
        raise CalcError("Expression too long")

    # Normalise display symbols and implicit multiplication
    expr = (
        expression.replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("^", "**")
        .replace("√", "sqrt")
        .replace("π", "pi")
        .replace(",", "")
        .strip()
    )
    if not expr: #dkjvk
        raise CalcError("Empty expression")

    # Factorial: 5! -> fact(5), (2+1)! -> fact((2+1))
    expr = re.sub(r"(\d+(?:\.\d+)?|\([^()]*\))!", r"fact(\1)", expr)
    # Percent: 50% -> (50/100)
    expr = re.sub(r"(\d+(?:\.\d+)?|\([^()]*\))%", r"(\1/100)", expr)
    # Implicit multiplication: 2(3) 2pi 2sqrt(4) (1+2)(3+4) 3(2)
    expr = re.sub(r"(\d|\))\s*(?=[a-zA-Z(])", r"\1*", expr)
    expr = re.sub(r"(pi|e)\s*(?=[\d(])", r"\1*", expr)
    expr = re.sub(r"\)\s*(?=\d)", r")*", expr)

    functions = build_functions(mode)

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise CalcError("Invalid expression")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            raise CalcError("Invalid value")
        if isinstance(node, ast.Name):
            if node.id in CONSTANTS:
                return CONSTANTS[node.id]
            raise CalcError(f"Unknown name: {node.id}")
        if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY_OPS:
            return UNARY_OPS[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in BIN_OPS:
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise CalcError("Cannot divide by zero")
            if isinstance(node.op, ast.Mod) and right == 0:
                raise CalcError("Cannot divide by zero")
            if isinstance(node.op, ast.Pow):
                if abs(right) > MAX_POWER:
                    raise CalcError("Exponent too large")
                if left == 0 and right < 0:
                    raise CalcError("Cannot divide by zero")
                if left < 0 and right != int(right):
                    raise CalcError("Complex result not supported")
            return BIN_OPS[type(node.op)](left, right)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in functions:
                raise CalcError("Unknown function")
            if len(node.args) != 1 or node.keywords:
                raise CalcError("Function takes one argument")
            return functions[node.func.id](_eval(node.args[0]))
        raise CalcError("Unsupported expression")

    try:
        result = _eval(tree)
    except OverflowError:
        raise CalcError("Number too large")
    except (ValueError, ZeroDivisionError):
        raise CalcError("Math error")

    if isinstance(result, complex) or math.isnan(result) or math.isinf(result):
        raise CalcError("Math error")
    return result


def format_result(value: float) -> str:
    """Clean display: 0.1+0.2 -> 0.3, 4.0 -> 4, 1e21 -> 1e+21."""
    value = round(value, 12)
    if value == 0:
        return "0"
    if abs(value) >= 1e15 or abs(value) < 1e-9:
        return f"{value:.10g}"
    if value == int(value):
        return str(int(value))
    return f"{value:.12f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Calculator API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CalcRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=MAX_EXPR_LEN)
    mode: Literal["deg", "rad"] = "deg"


class CalcResponse(BaseModel):
    id: int
    expression: str
    result: str


class HistoryItem(BaseModel):
    id: int
    expression: str
    result: str
    created_at: str


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/calculate", response_model=CalcResponse)
def calculate(req: CalcRequest):
    try:
        result = format_result(evaluate(req.expression, req.mode))
    except CalcError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with get_db() as db:
        cur = db.execute(
            "INSERT INTO history (expression, result) VALUES (?, ?)",
            (req.expression, result),
        )
        new_id = cur.lastrowid
    return CalcResponse(id=new_id, expression=req.expression, result=result)


@app.get("/api/history", response_model=list[HistoryItem])
def get_history(limit: int = 100):
    limit = max(1, min(limit, 500))
    with get_db() as db:
        rows = db.execute(
            "SELECT id, expression, result, created_at FROM history "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.delete("/api/history/{item_id}")
def delete_history_item(item_id: int):
    with get_db() as db:
        cur = db.execute("DELETE FROM history WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="History item not found")
    return {"deleted": item_id}


@app.delete("/api/history")
def clear_history():
    with get_db() as db:
        db.execute("DELETE FROM history")
    return {"cleared": True}
