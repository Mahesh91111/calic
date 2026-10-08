# Calculator App (FastAPI + React)

A scientific calculator with persistent history.

- **Backend:** Python + FastAPI + SQLite (history is stored in `backend/history.db`)
- **Frontend:** React (Vite)

## Features
- Basic operations: `+ − × ÷`, decimals, brackets, `%`, `±`
- Scientific: `sin cos tan log ln √ x² xʸ n! π e 1/x` with DEG/RAD toggle
- Safe expression evaluation (no `eval`), divide-by-zero and domain errors handled
- History saved in the database: click an item to reuse it, delete one, or clear all
- Keyboard support: digits, `+ - * / ^ % ! ( )`, `Enter` (=), `Backspace`, `Esc` (clear)

## Run the backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn main:app --reload
```
API runs at http://127.0.0.1:8000 (docs at `/docs`).

## Run the frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## API
| Method | Path | Description |
|---|---|---|
| POST | `/api/calculate` | body `{ "expression": "2+3×4", "mode": "deg" }` |
| GET | `/api/history` | previous calculations, newest first |
| DELETE | `/api/history/{id}` | delete one item |
| DELETE | `/api/history` | clear all |
| GET | `/api/health` | health check |

## Structure
```
calcuator/
├── backend/
│   ├── main.py
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        └── styles.css
```
