"""
ConceptDrift task generator.

Generates 30 tasks across 5 families (A-E), each with 6 drift levels.
All data is synthetic and deterministic (fixed seed) for reproducibility.
"""

import csv
import json
import hashlib
import logging
import random
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from benchmarks.tasks.schema import DriftTask

logger = logging.getLogger(__name__)

RANDOM_SEED = 42
STOCK_DIR_DEFAULT = "workspace/output/data/indiv-stock"
DESCRIPTIONS_CSV_DEFAULT = "workspace/output/data/stock-descriptions.csv"

FAMILY_NAMES = {
    "A": "stock_analysis",
    "B": "portfolio_risk",
    "C": "economic_indicators",
    "D": "github_issues",
    "E": "fusion",
    "F": "composition",  # Explicit cross-family composition tasks
}

# Drift type from taxonomy (drift_index 1->6)
DRIFT_TYPE_BY_INDEX = {
    1: "none",
    2: "schema_rename",
    3: "field_addition",
    4: "structure_change",
    5: "logic_change",
    6: "combined",
}

DRIFT_LEVELS = {1: "none", 2: "minor", 3: "minor", 4: "moderate", 5: "moderate", 6: "major"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_id(family: str, index: int) -> str:
    return f"{family}{index}"


def _load_stock_csv(path: Path) -> List[Dict[str, str]]:
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _load_descriptions(path: Path) -> Dict[str, Dict[str, str]]:
    """Load stock-descriptions.csv into {ticker: {sector, full name, ...}}."""
    out: Dict[str, Dict[str, str]] = {}
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out[row["ticker"]] = row
    return out


def _synth_stock_rows(ticker: str, n: int = 120, seed: int = RANDOM_SEED) -> List[Dict[str, Any]]:
    """Generate n synthetic daily OHLCV rows for a ticker (deterministic)."""
    rng = random.Random(seed + hash(ticker) % 10**6)
    price = rng.uniform(50, 500)
    rows = []
    for i in range(n):
        change = rng.gauss(0, price * 0.015)
        open_ = round(price + rng.uniform(-1, 1), 2)
        close = round(price + change, 2)
        high = round(max(open_, close) + rng.uniform(0, 2), 2)
        low = round(min(open_, close) - rng.uniform(0, 2), 2)
        volume = rng.randint(1_000_000, 50_000_000)
        rows.append({
            "Date": f"2024-{(i // 30) + 1:02d}-{(i % 28) + 1:02d}",
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Adjusted Close": close,
            "Volume": volume,
        })
        price = close
    return rows


def _synth_economic_series(name: str, n: int = 60, seed: int = RANDOM_SEED) -> List[Dict[str, Any]]:
    """Generate synthetic quarterly economic data."""
    rng = random.Random(seed + hash(name) % 10**6)
    base = rng.uniform(80, 120)
    rows = []
    for i in range(n):
        year = 2000 + i // 4
        q = (i % 4) + 1
        val = round(base + rng.gauss(0, base * 0.02), 4)
        base = val
        rows.append({"year": year, "quarter": q, "period": f"{year}Q{q}", "value": val})
    return rows


def _synth_github_issues(repo: str, n: int = 200, seed: int = RANDOM_SEED) -> List[Dict[str, Any]]:
    """Generate synthetic GitHub issues with labels, timestamps, bodies."""
    rng = random.Random(seed + hash(repo) % 10**6)
    labels_pool = ["bug", "enhancement", "documentation", "performance", "breaking-change",
                   "good first issue", "help wanted", "question", "wontfix", "duplicate"]
    users_pool = [f"user_{i}" for i in range(30)]
    sentiment_words_pos = ["great", "thanks", "works", "awesome", "fixed", "love", "excellent"]
    sentiment_words_neg = ["broken", "crash", "fail", "error", "regression", "slow", "blocker"]
    issues = []
    for i in range(n):
        is_neg = rng.random() < 0.4
        body_words = rng.choices(sentiment_words_neg if is_neg else sentiment_words_pos, k=rng.randint(5, 20))
        body = " ".join(body_words) + f" in module {rng.choice(['core', 'api', 'cli', 'db', 'auth', 'ui'])}"
        issues.append({
            "number": i + 1,
            "title": f"Issue #{i+1}: {'Bug' if is_neg else 'Feature'} report",
            "state": rng.choice(["open", "closed"]),
            "labels": [{"name": l} for l in rng.sample(labels_pool, k=rng.randint(1, 3))],
            "user": {"login": rng.choice(users_pool)},
            "created_at": f"2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}T{rng.randint(0,23):02d}:00:00Z",
            "body": body,
            "comments": rng.randint(0, 25),
            "reactions": {"total_count": rng.randint(0, 15)},
        })
    return issues


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_json_keys(output: Any, required_keys: List[str]) -> bool:
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return False
    if isinstance(output, dict):
        return all(k in output for k in required_keys)
    return False


def _validate_ds1000_execution(candidate: Any, context: Any) -> bool:
    """
    Validate generated code using DS-1000's test_execution from code_context.

    Args:
        candidate: Generated code string (or the full solution)
        context: dict with keys: code_context, prompt, validator="ds1000_execution"

    Returns:
        True if test_execution passes.
    """
    if not isinstance(context, dict):
        return False
    code_context = context.get("code_context") or ""
    prompt = context.get("prompt") or ""

    if not code_context:
        return False

    candidate_str = candidate if isinstance(candidate, str) else str(candidate)
    if not candidate_str.strip():
        return False

    # Build full solution: replace [insert] in prompt with generated code
    if "[insert]" in prompt:
        full_code = prompt.replace("[insert]", candidate_str)
    else:
        full_code = candidate_str

    try:
        # Provide pandas/numpy for DS-1000 code_context (Pandas tasks need these)
        local_ns: Dict[str, Any] = {}
        try:
            import pandas as pd  # noqa: F401
            import numpy as np  # noqa: F401
            local_ns["pd"] = pd
            local_ns["np"] = np
            local_ns["pandas"] = __import__("pandas")
            local_ns["numpy"] = __import__("numpy")
        except ImportError:
            pass
        exec(code_context, local_ns)
        test_execution = local_ns.get("test_execution")
        if not callable(test_execution):
            return False
        result = test_execution(full_code)
        # DS-1000 test_execution returns None on pass (no exception); raises on fail
        return result is None or bool(result)
    except Exception:
        return False


def _validate_bigcode_execution(candidate: Any, context: Any) -> bool:
    """
    Validate BigCodeBench generated code using unit tests.
    
    The code_prompt contains the function signature + imports.
    The candidate (or canonical_solution) contains the indented function body.
    We simply concatenate them to get a complete, executable function.
    """
    if not isinstance(context, dict):
        return False
    
    test_code = context.get("test_code") or ""
    code_prompt = context.get("code_prompt") or ""
    entry_point = context.get("entry_point") or "task_func"
    
    if not test_code:
        return False
    
    candidate_str = candidate if isinstance(candidate, str) else str(candidate)
    if not candidate_str.strip():
        return False
    
    import re
    
    # Extract code from markdown if present
    code_block_match = re.search(r'```python\s*(.*?)\s*```', candidate_str, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate_str = code_block_match.group(1)
    else:
        code_block_match = re.search(r'```\s*(.*?)\s*```', candidate_str, re.DOTALL)
        if code_block_match:
            candidate_str = code_block_match.group(1)
    
    # Clean up the candidate - remove any leading blank lines
    candidate_str = candidate_str.rstrip()
    
    # THE KEY FIX: Concatenate code_prompt + candidate body
    # code_prompt has: imports + "def task_func(args):"
    # candidate has:   "    # body lines..."
    if code_prompt:
        full_code = code_prompt.rstrip() + '\n' + candidate_str
    else:
        # Fallback: wrap in function if no code_prompt
        full_code = f"def {entry_point}():\n    " + candidate_str.replace('\n', '\n    ')
    
    try:
        local_ns: Dict[str, Any] = {}
        
        try:
            import io
            import sys
            import unittest
            local_ns.update({"io": io, "sys": sys, "unittest": unittest})
        except ImportError:
            pass
        
        # Execute the solution
        exec(full_code, local_ns)
        
        # Execute the test
        exec(test_code, local_ns)
        
        # Find and run Test class
        test_class = None
        for name, obj in local_ns.items():
            if isinstance(obj, type) and name.startswith("Test"):
                test_class = obj
                break
        
        if test_class:
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
            result = runner.run(suite)
            return result.wasSuccessful()
        
        return entry_point in local_ns
        
    except Exception:
        return False





def _validate_humaneval(candidate: Any, context: Any) -> bool:
    """
    Validate HumanEval solution by executing test code against candidate.
    Similar to BigCode but HumanEval uses direct function definitions.
    """
    if not isinstance(context, dict):
        return False
    
    test_code = context.get("test") or context.get("test_code") or ""
    entry_point = context.get("entry_point") or "candidate"
    
    if not test_code:
        return False
    
    candidate_str = candidate if isinstance(candidate, str) else str(candidate)
    if not candidate_str.strip():
        return False
    
    import re
    
    # Extract code from markdown if present
    code_block_match = re.search(r"```python\s*(.*?)\s*```", candidate_str, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate_str = code_block_match.group(1)
    else:
        code_block_match = re.search(r"```\s*(.*?)\s*```", candidate_str, re.DOTALL)
        if code_block_match:
            candidate_str = code_block_match.group(1)
    
    candidate_str = candidate_str.rstrip()
    
    try:
        local_ns: Dict[str, Any] = {}
        
        try:
            import io
            import sys
            import unittest
            local_ns.update({"io": io, "sys": sys, "unittest": unittest})
        except ImportError:
            pass
        
        # Execute the solution
        exec(candidate_str, local_ns)
        
        # Execute the test
        exec(test_code, local_ns)
        
        # Find and run Test class
        test_class = None
        for name, obj in local_ns.items():
            if isinstance(obj, type) and name.startswith("Test"):
                test_class = obj
                break
        
        if test_class:
            suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0)
            result = runner.run(suite)
            return result.wasSuccessful()
        
        return entry_point in local_ns
        
    except Exception:
        return False

def _validate_spider_sql(candidate: Any, context: Any) -> bool:
    """
    Validate SQL query for Spider text-to-SQL tasks.
    
    Basic validation: check SQL syntax is valid using SQLite parser.
    Future: could compare against expected query structure.
    """
    if not isinstance(context, dict):
        return False
    
    candidate_str = candidate if isinstance(candidate, str) else str(candidate)
    if not candidate_str.strip():
        return False
    
    # Clean up the candidate - extract SQL from various formats
    import re
    
    # First try to find SQL in markdown code blocks
    code_block_match = re.search(r'```sql\s*(.*?)\s*```', candidate_str, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        candidate_str = code_block_match.group(1)
    else:
        # Try generic code block
        code_block_match = re.search(r'```\s*(.*?)\s*```', candidate_str, re.DOTALL)
        if code_block_match:
            candidate_str = code_block_match.group(1)
    
    # Remove comment lines (lines starting with #)
    lines = candidate_str.split('\n')
    sql_lines = [line for line in lines if not line.strip().startswith('#')]
    candidate_str = '\n'.join(sql_lines).strip()
    
    # Extract just the SQL statement (look for SELECT, INSERT, UPDATE, DELETE, etc.)
    # Require the statement to end with semicolon for proper SQL
    sql_match = re.search(r'(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|WITH)\s+[^;]+;', 
                          candidate_str, re.DOTALL | re.IGNORECASE)
    if sql_match:
        candidate_str = sql_match.group(0)
    else:
        # No semicolon - might be incomplete SQL
        return False
    
    candidate_str = candidate_str.rstrip()
    if not candidate_str:
        return False
    
    # Strict SQL validation using sqlparse if available
    try:
        import sqlparse
        # Parse the SQL - this will raise an exception for syntax errors
        parsed = sqlparse.parse(candidate_str)
        if parsed and len(parsed) > 0:
            statement = parsed[0]
            # Check it has actual tokens (not just whitespace)
            tokens = [t for t in statement.tokens if not t.is_whitespace]
            if len(tokens) >= 2:  # At least command + something
                first_token = str(tokens[0]).upper()
                valid_starts = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 
                               'DROP', 'ALTER', 'WITH', 'GRANT', 'REVOKE')
                if first_token in valid_starts:
                    return True
        return False
    except ImportError:
        # Fallback: strict regex validation
        # Must have proper SQL structure with semicolon
        upper = candidate_str.upper()
        # Check for SELECT ... FROM pattern
        if re.search(r'SELECT\s+.+\s+FROM\s+\w+', upper):
            return True
        # Check for other statement types with proper structure
        if re.search(r'(INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+\w+', upper):
            return True
        return False
    except Exception:
        return False


def _extract_spider2_sql(raw: str) -> str:
    """Extract clean SQL from candidate (markdown, comments)."""
    import re
    s = raw if isinstance(raw, str) else str(raw)
    code_block_match = re.search(r'```sql\s*(.*?)\s*```', s, re.DOTALL | re.IGNORECASE)
    if code_block_match:
        s = code_block_match.group(1)
    else:
        code_block_match = re.search(r'```\s*(.*?)\s*```', s, re.DOTALL)
        if code_block_match:
            s = code_block_match.group(1)
    lines = []
    for line in s.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('--'):
            lines.append(line)
    return '\n'.join(lines).strip()


def _execute_sql_and_compare(db_path: Path, candidate_sql: str, gold_sql: str) -> bool:
    """Execute both SQLs against SQLite DB and compare result sets (order-insensitive)."""
    import sqlite3
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        try:
            cur.execute(candidate_sql)
            cand_rows = [tuple(r) for r in cur.fetchall()]
        except sqlite3.Error:
            return False
        try:
            cur.execute(gold_sql)
            gold_rows = [tuple(r) for r in cur.fetchall()]
        except sqlite3.Error:
            conn.close()
            return False
        conn.close()
        # Compare as multisets (order-independent)
        return sorted(cand_rows) == sorted(gold_rows)
    except Exception:
        return False


def _validate_spider2_sql(candidate: Any, context: Any) -> bool:
    """
    Validate SQL query for Spider 2.0 / BIRD text-to-SQL tasks.
    
    When BIRD_DATABASES_DIR is set (path to train_databases/ from BIRD train.zip),
    uses execution-based validation: run both candidate and gold SQL, compare results.
    Otherwise falls back to syntax + structure validation only.
    """
    if not isinstance(context, dict):
        return False
    
    candidate_str = candidate if isinstance(candidate, str) else str(candidate)
    if not candidate_str.strip():
        return False
    
    ground_truth_sql = context.get("sql", "")
    db_id = context.get("db_id", "")
    difficulty = context.get("difficulty", "medium")
    
    import os
    import re
    
    candidate_sql = _extract_spider2_sql(candidate_str)
    if not candidate_sql:
        return False
    
    # Execution-based validation when BIRD databases are available
    db_dir = os.environ.get("BIRD_DATABASES_DIR")
    if db_dir and db_id and ground_truth_sql:
        base = Path(db_dir)
        # BIRD train.zip: extract contains train_databases/{db_id}/ with sqlite file
        for db_folder in [base / "train_databases" / db_id, base / db_id]:
            if not db_folder.exists() or not db_folder.is_dir():
                continue
            # Look for .sqlite or .db file in folder
            for db_path in list(db_folder.glob("*.sqlite")) + list(db_folder.glob("*.db")):
                if db_path.is_file() and _execute_sql_and_compare(db_path, candidate_sql, ground_truth_sql):
                    return True
                if db_path.is_file():
                    return False
            # Check sqlite as filename (no extension)
            sqlite_file = db_folder / "sqlite"
            if sqlite_file.is_file() and _execute_sql_and_compare(sqlite_file, candidate_sql, ground_truth_sql):
                return True
            if sqlite_file.is_file():
                return False
            # Check sqlite/ subfolder
            for db_path in (db_folder / "sqlite").glob("*.sqlite") if (db_folder / "sqlite").is_dir() else []:
                if _execute_sql_and_compare(db_path, candidate_sql, ground_truth_sql):
                    return True
                return False
        logger.debug(f"BIRD_DATABASES_DIR set but DB not found for {db_id}, falling back to syntax validation")
    
    # Fallback: syntax + structure validation (does NOT verify correctness)
    upper = candidate_sql.upper()

    # Required SQL keywords based on complexity
    has_select = 'SELECT' in upper
    has_from = 'FROM' in upper
    
    # Must have basic structure
    if not (has_select and has_from):
        return False
    
    # Try to use sqlparse for syntax validation
    try:
        import sqlparse
        parsed = sqlparse.parse(candidate_sql)

        if not parsed:
            return False
        
        # Check if at least one statement is valid
        for statement in parsed:
            tokens = [str(t).upper() for t in statement.tokens if not t.is_whitespace]
            if tokens:
                first_keyword = tokens[0]
                if first_keyword in ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'WITH', 'CREATE'):
                    # Valid SQL statement found
                    # For Spider 2.0, also check complexity
                    if difficulty in ['moderate', 'challenging', 'hard']:
                        # Moderate+ difficulty should have some complexity
                        has_complexity = (
                            'JOIN' in upper or
                            'WHERE' in upper or
                            'GROUP' in upper or
                            'ORDER' in upper or
                            'HAVING' in upper or
                            'WITH' in upper or  # CTE
                            'SUBSTR' in upper or
                            'COUNT' in upper or
                            'SUM' in upper or
                            'AVG' in upper
                        )
                        if not has_complexity:
                            return False
                    return True
        
        return False
        
    except ImportError:
        # Fallback: strict regex validation
        # For BIRD/Spider 2.0, require more complex patterns
        if difficulty in ['moderate', 'challenging', 'hard']:
            # Should have some complexity marker
            complexity_patterns = [
                r'JOIN\s+\w+',
                r'WHERE\s+.+',
                r'GROUP\s+BY',
                r'ORDER\s+BY',
                r'HAVING\s+.+',
                r'WITH\s+\w+\s+AS',
                r'SUBSTR\s*\(',
                r'COUNT\s*\(',
                r'SUM\s*\(',
                r'AVG\s*\(',
            ]
            has_complexity = any(re.search(p, upper) for p in complexity_patterns)
            if not has_complexity:
                return False
        
        # Basic SELECT ... FROM validation
        if re.search(r'SELECT\s+.+\s+FROM\s+\w+', upper):
            return True
        return False
    except Exception:
        return False


def _validate_numeric_close(output: Any, expected: Any, rtol: float = 0.05) -> bool:
    """Check numeric values are within relative tolerance."""
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return False
    if isinstance(expected, str):
        try:
            expected = json.loads(expected)
        except (json.JSONDecodeError, TypeError):
            return False
    if isinstance(output, dict) and isinstance(expected, dict):
        for key in expected:
            if key not in output:
                return False
            try:
                o, e = float(output[key]), float(expected[key])
                if e == 0:
                    if abs(o) > 1e-6:
                        return False
                elif abs(o - e) / abs(e) > rtol:
                    return False
            except (ValueError, TypeError):
                if str(output[key]) != str(expected[key]):
                    return False
        return True
    return output == expected


# ---------------------------------------------------------------------------
# Family A — Stock Analysis
# ---------------------------------------------------------------------------

def _family_A(tickers: List[str], data_dir: Path) -> List[DriftTask]:
    """Generate 6 stock analysis tasks with progressive drift."""
    ticker = tickers[0]
    rows = _synth_stock_rows(ticker, 120)

    # Pre-compute ground truths
    closes = [r["Close"] for r in rows]
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    avg_return = sum(returns) / len(returns)

    # A1 data
    a1_csv_path = data_dir / "A1_stock.csv"

    # A2: rename Close -> Closing_Price
    a2_rows = [{**r, "Closing_Price": r.pop("Close")} for r in [dict(r) for r in rows]]

    # A3: add volatility (20-day rolling std)
    import math
    vol_20 = []
    for i in range(19, len(returns)):
        window = returns[i-19:i+1]
        mean = sum(window) / 20
        var = sum((x - mean) ** 2 for x in window) / 19
        vol_20.append(round(math.sqrt(var), 6))
    avg_vol = round(sum(vol_20) / len(vol_20), 6)

    # A4: grouped by sector — needs a second ticker
    ticker2 = tickers[1] if len(tickers) > 1 else tickers[0]
    rows2 = _synth_stock_rows(ticker2, 120)

    # A5: correlation matrix (2 stocks)
    closes2 = [r["Close"] for r in rows2]
    returns2 = [(closes2[i] - closes2[i-1]) / closes2[i-1] for i in range(1, len(closes2))]
    n = min(len(returns), len(returns2))
    mean1 = sum(returns[:n]) / n
    mean2 = sum(returns2[:n]) / n
    cov = sum((returns[i] - mean1) * (returns2[i] - mean2) for i in range(n)) / (n - 1)
    std1 = math.sqrt(sum((returns[i] - mean1) ** 2 for i in range(n)) / (n - 1))
    std2 = math.sqrt(sum((returns2[i] - mean2) ** 2 for i in range(n)) / (n - 1))
    corr_12 = round(cov / (std1 * std2), 6) if std1 and std2 else 0.0

    # A6: beta vs SPY
    spy_rows = _synth_stock_rows("SPY", 120)
    spy_closes = [r["Close"] for r in spy_rows]
    spy_returns = [(spy_closes[i] - spy_closes[i-1]) / spy_closes[i-1] for i in range(1, len(spy_closes))]
    n_beta = min(len(returns), len(spy_returns))
    spy_mean = sum(spy_returns[:n_beta]) / n_beta
    cov_spy = sum((returns[i] - mean1) * (spy_returns[i] - spy_mean) for i in range(n_beta)) / (n_beta - 1)
    var_spy = sum((spy_returns[i] - spy_mean) ** 2 for i in range(n_beta)) / (n_beta - 1)
    beta = round(cov_spy / var_spy, 6) if var_spy else 0.0

    tasks = []

    # A1 — baseline
    tasks.append(DriftTask(
        id="A1", name="A1_stock_daily_returns", difficulty="easy",
        description="Calculate daily returns from stock CSV",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="none", drift_index=1,
        drift_description="Baseline: calculate daily returns from Close column",
        prompt=(
            f"Read the CSV file 'A1_stock.csv' containing stock price data for {ticker}.\n"
            "Calculate the daily return for each day as (Close[i] - Close[i-1]) / Close[i-1].\n"
            "Write a JSON file 'answer.json' with keys:\n"
            '  - "avg_daily_return": the mean daily return (float)\n'
            '  - "num_days": number of return observations (int)\n'
            '  - "ticker": the ticker symbol (str)\n'
        ),
        input_data={"rows": rows, "file": "A1_stock.csv", "ticker": ticker},
        ground_truth={"avg_daily_return": round(avg_return, 6), "num_days": len(returns), "ticker": ticker},
        objective_fn_name="validate_numeric_close",
    ))

    # A2 — minor drift: column renamed
    tasks.append(DriftTask(
        id="A2", name="A2_stock_returns_renamed", difficulty="easy",
        description="Calculate daily returns — column renamed",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="minor", drift_index=2,
        prior_task_id="A1", oracle_skill_id="A1",
        drift_description="Column 'Close' renamed to 'Closing_Price'",
        prompt=(
            f"Read the CSV file 'A2_stock.csv' containing stock price data for {ticker}.\n"
            "Calculate the daily return for each day as (Closing_Price[i] - Closing_Price[i-1]) / Closing_Price[i-1].\n"
            "Write a JSON file 'answer.json' with keys:\n"
            '  - "avg_daily_return": the mean daily return (float)\n'
            '  - "num_days": number of return observations (int)\n'
            '  - "ticker": the ticker symbol (str)\n'
        ),
        input_data={"rows": a2_rows, "file": "A2_stock.csv", "ticker": ticker},
        ground_truth={"avg_daily_return": round(avg_return, 6), "num_days": len(returns), "ticker": ticker},
        objective_fn_name="validate_numeric_close",
    ))

    # A3 — minor drift: add volatility metric
    tasks.append(DriftTask(
        id="A3", name="A3_stock_returns_volatility", difficulty="easy",
        description="Calculate daily returns AND 20-day rolling volatility",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="minor", drift_index=3,
        prior_task_id="A2", oracle_skill_id="A2",
        drift_description="New requirement: also compute 20-day rolling volatility",
        prompt=(
            f"Read the CSV file 'A3_stock.csv' containing stock price data for {ticker}.\n"
            "1. Calculate daily returns from the 'Close' column.\n"
            "2. Compute 20-day rolling standard deviation of returns (sample std).\n"
            "Write a JSON file 'answer.json' with keys:\n"
            '  - "avg_daily_return": mean daily return (float)\n'
            '  - "avg_volatility_20d": mean of the 20-day rolling std values (float)\n'
            '  - "num_vol_observations": how many 20-day windows (int)\n'
        ),
        input_data={"rows": rows, "file": "A3_stock.csv", "ticker": ticker},
        ground_truth={
            "avg_daily_return": round(avg_return, 6),
            "avg_volatility_20d": avg_vol,
            "num_vol_observations": len(vol_20),
        },
        objective_fn_name="validate_numeric_close",
    ))

    # A4 — moderate drift: nested output grouped by sector
    descs = {ticker: {"sector": "Technology"}, ticker2: {"sector": "Finance"}}
    tasks.append(DriftTask(
        id="A4", name="A4_stock_grouped_by_sector", difficulty="medium",
        description="Calculate returns grouped by sector (nested output)",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="moderate", drift_index=4,
        prior_task_id="A3", oracle_skill_id="A3",
        drift_description="Output must be nested by sector; requires joining with descriptions",
        prompt=(
            "Read TWO CSV files:\n"
            f"  - 'A4_stock1.csv' (ticker: {ticker})\n"
            f"  - 'A4_stock2.csv' (ticker: {ticker2})\n"
            "Also read 'A4_descriptions.json' which maps ticker -> sector.\n"
            "For each stock calculate the average daily return.\n"
            "Write a JSON file 'answer.json' with structure:\n"
            "{\n"
            '  "<sector>": {\n'
            '    "<ticker>": {"avg_daily_return": <float>}\n'
            "  }\n"
            "}\n"
        ),
        input_data={
            "rows1": rows, "rows2": rows2,
            "file1": "A4_stock1.csv", "file2": "A4_stock2.csv",
            "descriptions": descs, "descriptions_file": "A4_descriptions.json",
        },
        ground_truth={
            descs[ticker]["sector"]: {ticker: {"avg_daily_return": round(avg_return, 6)}},
            descs[ticker2]["sector"]: {
                ticker2: {"avg_daily_return": round(
                    sum(returns2) / len(returns2), 6)}},
        },
        objective_fn_name="validate_json_keys",
    ))

    # A5 — moderate drift: correlation matrix
    tasks.append(DriftTask(
        id="A5", name="A5_stock_correlation_matrix", difficulty="medium",
        description="Calculate pairwise return correlations",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="moderate", drift_index=5,
        prior_task_id="A4", oracle_skill_id="A4",
        drift_description="New output: pairwise correlation matrix between two stocks",
        prompt=(
            "Read two stock CSV files:\n"
            f"  - 'A5_stock1.csv' (ticker: {ticker})\n"
            f"  - 'A5_stock2.csv' (ticker: {ticker2})\n"
            "Calculate daily returns for each stock, then compute the Pearson "
            "correlation coefficient between the two return series.\n"
            "Write a JSON file 'answer.json' with keys:\n"
            f'  - "correlation_{ticker}_{ticker2}": the Pearson correlation (float)\n'
            '  - "num_observations": number of paired observations (int)\n'
        ),
        input_data={
            "rows1": rows, "rows2": rows2,
            "file1": "A5_stock1.csv", "file2": "A5_stock2.csv",
        },
        ground_truth={
            f"correlation_{ticker}_{ticker2}": corr_12,
            "num_observations": n,
        },
        objective_fn_name="validate_numeric_close",
    ))

    # A6 — major drift: beta vs SPY + outlier removal
    tasks.append(DriftTask(
        id="A6", name="A6_stock_beta_regression", difficulty="hard",
        description="Calculate stock beta vs SPY with outlier removal",
        validation_type="custom", category="stock_analysis",
        family="A", drift_level="major", drift_index=6,
        prior_task_id="A5", oracle_skill_id="A5",
        drift_description="Business logic change: regression beta vs SPY + outlier removal",
        prompt=(
            f"Read 'A6_stock.csv' ({ticker}) and 'A6_spy.csv' (SPY benchmark).\n"
            "1. Calculate daily returns for both.\n"
            "2. Remove outlier days where either return exceeds ±3 standard deviations.\n"
            "3. Regress stock returns on SPY returns (OLS) to compute beta.\n"
            "Write a JSON file 'answer.json' with keys:\n"
            '  - "beta": the regression slope (float)\n'
            '  - "outliers_removed": count of removed outlier days (int)\n'
            f'  - "ticker": "{ticker}"\n'
        ),
        input_data={
            "rows": rows, "spy_rows": spy_rows,
            "file": "A6_stock.csv", "spy_file": "A6_spy.csv",
        },
        ground_truth={"beta": beta, "outliers_removed": 0, "ticker": ticker},
        objective_fn_name="validate_numeric_close",
    ))

    return tasks


# ---------------------------------------------------------------------------
# Family B — Portfolio Risk
# ---------------------------------------------------------------------------

def _family_B(tickers: List[str]) -> List[DriftTask]:
    """Generate 6 portfolio risk tasks with progressive drift."""
    import math

    t1, t2 = tickers[0], tickers[1] if len(tickers) > 1 else tickers[0]
    rows1 = _synth_stock_rows(t1, 120)
    rows2 = _synth_stock_rows(t2, 120)
    closes1 = [r["Close"] for r in rows1]
    closes2 = [r["Close"] for r in rows2]
    rets1 = [(closes1[i] - closes1[i-1]) / closes1[i-1] for i in range(1, len(closes1))]
    rets2 = [(closes2[i] - closes2[i-1]) / closes2[i-1] for i in range(1, len(closes2))]

    # B1 ground truth — VaR 95% for single stock
    sorted_r = sorted(rets1)
    var_idx = max(0, int(len(sorted_r) * 0.05) - 1)
    var_95 = round(sorted_r[var_idx], 6)

    # B3 — Sharpe ratio
    avg_r = sum(rets1) / len(rets1)
    std_r = math.sqrt(sum((x - avg_r)**2 for x in rets1) / (len(rets1) - 1))
    sharpe = round(avg_r / std_r * math.sqrt(252), 6) if std_r else 0.0

    # 5-stock synthetic data for B4/B5/B6
    multi_tickers = tickers[:5] if len(tickers) >= 5 else tickers * 3
    multi_tickers = multi_tickers[:5]
    weights = [0.3, 0.25, 0.2, 0.15, 0.1]
    multi_rets = []
    for t in multi_tickers:
        rows_t = _synth_stock_rows(t, 120)
        c = [r["Close"] for r in rows_t]
        multi_rets.append([(c[i] - c[i-1]) / c[i-1] for i in range(1, len(c))])

    n_obs = min(len(r) for r in multi_rets)
    port_rets = []
    for i in range(n_obs):
        port_rets.append(sum(w * multi_rets[j][i] for j, w in enumerate(weights)))
    port_sorted = sorted(port_rets)
    port_var = round(port_sorted[max(0, int(len(port_sorted) * 0.05) - 1)], 6)

    tasks = []

    tasks.append(DriftTask(
        id="B1", name="B1_single_stock_var", difficulty="easy",
        description="Calculate single-stock Value-at-Risk (95%)",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="none", drift_index=1,
        drift_description="Baseline: VaR at 95% confidence for one stock",
        prompt=(
            f"Read 'B1_stock.csv' containing daily prices for {t1}.\n"
            "Calculate the 95% historical Value-at-Risk (VaR) from daily returns.\n"
            "VaR is the 5th percentile of the return distribution.\n"
            "Write 'answer.json' with:\n"
            '  - "var_95": the VaR value (float, negative expected)\n'
            '  - "num_days": number of return observations (int)\n'
        ),
        input_data={"rows": rows1, "file": "B1_stock.csv", "ticker": t1},
        ground_truth={"var_95": var_95, "num_days": len(rets1)},
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="B2", name="B2_two_stock_portfolio_var", difficulty="easy",
        description="Two-stock portfolio VaR with correlation",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="minor", drift_index=2,
        prior_task_id="B1", oracle_skill_id="B1",
        drift_description="Now a 2-stock equal-weight portfolio instead of single stock",
        prompt=(
            f"Read 'B2_stock1.csv' ({t1}) and 'B2_stock2.csv' ({t2}).\n"
            "Form an equal-weight portfolio (50/50).\n"
            "Calculate portfolio daily returns and compute 95% VaR.\n"
            "Write 'answer.json' with:\n"
            '  - "portfolio_var_95": the VaR value (float)\n'
            '  - "num_days": number of observations (int)\n'
        ),
        input_data={
            "rows1": rows1, "rows2": rows2,
            "file1": "B2_stock1.csv", "file2": "B2_stock2.csv",
        },
        ground_truth={
            "portfolio_var_95": round(sorted(
                [0.5 * rets1[i] + 0.5 * rets2[i] for i in range(min(len(rets1), len(rets2)))]
            )[max(0, int(min(len(rets1), len(rets2)) * 0.05) - 1)], 6),
            "num_days": min(len(rets1), len(rets2)),
        },
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="B3", name="B3_sharpe_ratio", difficulty="easy",
        description="Add Sharpe ratio to single-stock analysis",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="minor", drift_index=3,
        prior_task_id="B2", oracle_skill_id="B2",
        drift_description="New metric: Sharpe ratio (annualised) added to output",
        prompt=(
            f"Read 'B3_stock.csv' ({t1}). Calculate:\n"
            "1. 95% VaR from daily returns\n"
            "2. Annualised Sharpe ratio (assume risk-free rate = 0, annualise with sqrt(252))\n"
            "Write 'answer.json' with:\n"
            '  - "var_95": VaR (float)\n'
            '  - "sharpe_ratio": annualised Sharpe (float)\n'
        ),
        input_data={"rows": rows1, "file": "B3_stock.csv", "ticker": t1},
        ground_truth={"var_95": var_95, "sharpe_ratio": sharpe},
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="B4", name="B4_multi_asset_weighted_var", difficulty="medium",
        description="5-stock weighted portfolio VaR",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="moderate", drift_index=4,
        prior_task_id="B3", oracle_skill_id="B3",
        drift_description="Scale to 5 stocks with specified weights",
        prompt=(
            "Read 5 stock CSV files: " +
            ", ".join(f"'B4_stock{i+1}.csv' ({multi_tickers[i]})" for i in range(5)) + ".\n"
            f"Portfolio weights: {weights}.\n"
            "Calculate the weighted portfolio daily returns and compute 95% VaR.\n"
            "Write 'answer.json' with:\n"
            '  - "portfolio_var_95": VaR (float)\n'
            '  - "num_days": observations (int)\n'
        ),
        input_data={
            "tickers": multi_tickers, "weights": weights,
            "files": [f"B4_stock{i+1}.csv" for i in range(5)],
        },
        ground_truth={"portfolio_var_95": port_var, "num_days": n_obs},
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="B5", name="B5_stress_test", difficulty="medium",
        description="Portfolio VaR with stress-test scenario",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="moderate", drift_index=5,
        prior_task_id="B4", oracle_skill_id="B4",
        drift_description="Add stress-test: shift all returns by -2% then re-compute VaR",
        prompt=(
            "Read 5 stock CSV files: " +
            ", ".join(f"'B5_stock{i+1}.csv' ({multi_tickers[i]})" for i in range(5)) + ".\n"
            f"Portfolio weights: {weights}.\n"
            "1. Calculate normal 95% VaR.\n"
            "2. Stress test: subtract 0.02 from every daily return and recompute VaR.\n"
            "Write 'answer.json' with:\n"
            '  - "portfolio_var_95": normal VaR (float)\n'
            '  - "stressed_var_95": stressed VaR (float)\n'
        ),
        input_data={
            "tickers": multi_tickers, "weights": weights,
            "files": [f"B5_stock{i+1}.csv" for i in range(5)],
        },
        ground_truth={
            "portfolio_var_95": port_var,
            "stressed_var_95": round(sorted(
                [r - 0.02 for r in port_rets]
            )[max(0, int(len(port_rets) * 0.05) - 1)], 6),
        },
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="B6", name="B6_rebalancing_risk_constraint", difficulty="hard",
        description="Minimum-variance rebalancing with risk constraint",
        validation_type="custom", category="portfolio_risk",
        family="B", drift_level="major", drift_index=6,
        prior_task_id="B5", oracle_skill_id="B5",
        drift_description="Business logic: check if portfolio VaR breaches -3% and flag for rebalancing",
        prompt=(
            "Read 5 stock CSV files: " +
            ", ".join(f"'B6_stock{i+1}.csv' ({multi_tickers[i]})" for i in range(5)) + ".\n"
            f"Portfolio weights: {weights}.\n"
            "1. Calculate weighted portfolio 95% VaR.\n"
            "2. If VaR < -0.03 (breach), flag 'needs_rebalancing': true.\n"
            "3. Compute max drawdown of the portfolio.\n"
            "Write 'answer.json' with:\n"
            '  - "portfolio_var_95": VaR (float)\n'
            '  - "needs_rebalancing": bool\n'
            '  - "max_drawdown": float\n'
        ),
        input_data={
            "tickers": multi_tickers, "weights": weights,
            "files": [f"B6_stock{i+1}.csv" for i in range(5)],
        },
        ground_truth={
            "portfolio_var_95": port_var,
            "needs_rebalancing": port_var < -0.03,
            "max_drawdown": round(min(
                min(port_rets[i] - max(port_rets[:i+1]) for i in range(1, len(port_rets))),
                0.0
            ), 6),
        },
        objective_fn_name="validate_numeric_close",
    ))

    return tasks


# ---------------------------------------------------------------------------
# Family C — Economic Indicators
# ---------------------------------------------------------------------------

def _family_C() -> List[DriftTask]:
    """Generate 6 economic indicator tasks with progressive drift."""
    import math

    cpi = _synth_economic_series("CPI", 60)
    gdp = _synth_economic_series("GDP", 60)
    consumption = _synth_economic_series("CONSUMPTION", 60)
    investment = _synth_economic_series("INVESTMENT", 60)

    cpi_vals = [r["value"] for r in cpi]
    gdp_vals = [r["value"] for r in gdp]

    # C1 ground truth: deflate GDP by CPI (base = first CPI value)
    base_cpi = cpi_vals[0]
    real_gdp = [round(gdp_vals[i] * base_cpi / cpi_vals[i], 4) for i in range(len(gdp_vals))]
    avg_real_gdp = round(sum(real_gdp) / len(real_gdp), 4)

    # C2: different base year (index 20)
    base_cpi_2 = cpi_vals[20]
    real_gdp_2 = [round(gdp_vals[i] * base_cpi_2 / cpi_vals[i], 4) for i in range(len(gdp_vals))]
    avg_real_gdp_2 = round(sum(real_gdp_2) / len(real_gdp_2), 4)

    tasks = []

    tasks.append(DriftTask(
        id="C1", name="C1_simple_deflation", difficulty="easy",
        description="Deflate nominal GDP by CPI",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="none", drift_index=1,
        drift_description="Baseline: deflate GDP using CPI with first-period base",
        prompt=(
            "Read 'C1_gdp.json' (nominal GDP) and 'C1_cpi.json' (CPI) — both quarterly.\n"
            "Deflate GDP: real_gdp[i] = nominal_gdp[i] * base_cpi / cpi[i], "
            "where base_cpi is the CPI value of the FIRST period.\n"
            "Write 'answer.json' with:\n"
            '  - "avg_real_gdp": mean of real GDP series (float)\n'
            '  - "num_periods": number of observations (int)\n'
        ),
        input_data={
            "gdp": gdp, "cpi": cpi,
            "gdp_file": "C1_gdp.json", "cpi_file": "C1_cpi.json",
        },
        ground_truth={"avg_real_gdp": avg_real_gdp, "num_periods": len(gdp)},
        objective_fn_name="validate_numeric_close",
    ))

    tasks.append(DriftTask(
        id="C2", name="C2_different_base_year", difficulty="easy",
        description="Deflate GDP — different base year",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="minor", drift_index=2,
        prior_task_id="C1", oracle_skill_id="C1",
        drift_description="Base year changed from first period to period index 20",
        prompt=(
            "Read 'C2_gdp.json' (nominal GDP) and 'C2_cpi.json' (CPI) — both quarterly.\n"
            "Deflate GDP using CPI with the base period at INDEX 20 (0-based).\n"
            "real_gdp[i] = nominal_gdp[i] * cpi[20] / cpi[i]\n"
            "Write 'answer.json' with:\n"
            '  - "avg_real_gdp": mean of real GDP series (float)\n'
            '  - "base_period": "2005Q1" (the period label at index 20)\n'
        ),
        input_data={
            "gdp": gdp, "cpi": cpi,
            "gdp_file": "C2_gdp.json", "cpi_file": "C2_cpi.json",
        },
        ground_truth={"avg_real_gdp": avg_real_gdp_2, "base_period": cpi[20]["period"]},
        objective_fn_name="validate_numeric_close",
    ))

    # C3 — HP filter (simplified: double exponential smoothing as proxy)
    alpha = 0.3
    smoothed = [real_gdp[0]]
    for i in range(1, len(real_gdp)):
        smoothed.append(round(alpha * real_gdp[i] + (1 - alpha) * smoothed[-1], 4))
    avg_trend = round(sum(smoothed) / len(smoothed), 4)

    tasks.append(DriftTask(
        id="C3", name="C3_trend_extraction", difficulty="medium",
        description="Deflate GDP + extract trend via exponential smoothing",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="minor", drift_index=3,
        prior_task_id="C2", oracle_skill_id="C2",
        drift_description="New requirement: apply exponential smoothing (alpha=0.3) for trend",
        prompt=(
            "Read 'C3_gdp.json' and 'C3_cpi.json'.\n"
            "1. Deflate GDP using first-period CPI base.\n"
            "2. Apply exponential smoothing to the real GDP series with alpha=0.3:\n"
            "   trend[0] = real_gdp[0]; trend[i] = 0.3*real_gdp[i] + 0.7*trend[i-1]\n"
            "Write 'answer.json' with:\n"
            '  - "avg_real_gdp": mean real GDP (float)\n'
            '  - "avg_trend": mean of the smoothed trend (float)\n'
        ),
        input_data={
            "gdp": gdp, "cpi": cpi,
            "gdp_file": "C3_gdp.json", "cpi_file": "C3_cpi.json",
        },
        ground_truth={"avg_real_gdp": avg_real_gdp, "avg_trend": avg_trend},
        objective_fn_name="validate_numeric_close",
    ))

    # C4 — seasonal adjustment (quarter means)
    q_sums = {1: 0, 2: 0, 3: 0, 4: 0}
    q_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for i, row in enumerate(gdp):
        q = row["quarter"]
        q_sums[q] += real_gdp[i]
        q_counts[q] += 1
    q_means = {q: round(q_sums[q] / q_counts[q], 4) for q in range(1, 5)}
    overall_mean = round(sum(real_gdp) / len(real_gdp), 4)
    seasonal_factors = {q: round(q_means[q] / overall_mean, 4) for q in range(1, 5)}

    tasks.append(DriftTask(
        id="C4", name="C4_seasonal_adjustment", difficulty="medium",
        description="Deflate + seasonal adjustment",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="moderate", drift_index=4,
        prior_task_id="C3", oracle_skill_id="C3",
        drift_description="Add seasonal adjustment: compute seasonal factors per quarter",
        prompt=(
            "Read 'C4_gdp.json' and 'C4_cpi.json'.\n"
            "1. Deflate GDP using first-period CPI base.\n"
            "2. Compute seasonal factor for each quarter:\n"
            "   factor_q = mean(real_gdp for quarter q) / overall_mean\n"
            "3. Seasonally adjust: sa_gdp[i] = real_gdp[i] / factor_q\n"
            "Write 'answer.json' with:\n"
            '  - "seasonal_factors": {"1": f1, "2": f2, "3": f3, "4": f4}\n'
            '  - "avg_seasonally_adjusted": mean of sa_gdp (float)\n'
        ),
        input_data={
            "gdp": gdp, "cpi": cpi,
            "gdp_file": "C4_gdp.json", "cpi_file": "C4_cpi.json",
        },
        ground_truth={
            "seasonal_factors": {str(q): v for q, v in seasonal_factors.items()},
            "avg_seasonally_adjusted": overall_mean,
        },
        objective_fn_name="validate_numeric_close",
    ))

    # C5 — multi-series correlation
    cons_vals = [r["value"] for r in consumption]
    inv_vals = [r["value"] for r in investment]
    n_c = min(len(cons_vals), len(inv_vals))
    mean_c = sum(cons_vals[:n_c]) / n_c
    mean_i = sum(inv_vals[:n_c]) / n_c
    cov_ci = sum((cons_vals[i] - mean_c) * (inv_vals[i] - mean_i) for i in range(n_c)) / (n_c - 1)
    std_c = math.sqrt(sum((cons_vals[i] - mean_c)**2 for i in range(n_c)) / (n_c - 1))
    std_i = math.sqrt(sum((inv_vals[i] - mean_i)**2 for i in range(n_c)) / (n_c - 1))
    corr_ci = round(cov_ci / (std_c * std_i), 6) if (std_c and std_i) else 0.0

    tasks.append(DriftTask(
        id="C5", name="C5_multi_series_correlation", difficulty="medium",
        description="Correlation between consumption and investment",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="moderate", drift_index=5,
        prior_task_id="C4", oracle_skill_id="C4",
        drift_description="New requirement: correlate consumption and investment series",
        prompt=(
            "Read 'C5_consumption.json' and 'C5_investment.json'.\n"
            "Compute the Pearson correlation between the two value series.\n"
            "Write 'answer.json' with:\n"
            '  - "correlation": Pearson r (float)\n'
            '  - "num_observations": int\n'
        ),
        input_data={
            "consumption": consumption, "investment": investment,
            "consumption_file": "C5_consumption.json",
            "investment_file": "C5_investment.json",
        },
        ground_truth={"correlation": corr_ci, "num_observations": n_c},
        objective_fn_name="validate_numeric_close",
    ))

    # C6 — forecasting (simple linear extrapolation)
    x = list(range(len(real_gdp)))
    x_mean = sum(x) / len(x)
    y_mean = sum(real_gdp) / len(real_gdp)
    slope = sum((x[i] - x_mean) * (real_gdp[i] - y_mean) for i in range(len(x))) / \
            sum((x[i] - x_mean) ** 2 for i in range(len(x)))
    intercept = y_mean - slope * x_mean
    next_4 = [round(intercept + slope * (len(x) + j), 4) for j in range(4)]

    tasks.append(DriftTask(
        id="C6", name="C6_linear_forecast", difficulty="hard",
        description="Deflate GDP + linear regression forecast",
        validation_type="custom", category="economic_indicators",
        family="C", drift_level="major", drift_index=6,
        prior_task_id="C5", oracle_skill_id="C5",
        drift_description="Major: add forecasting via linear regression for next 4 quarters",
        prompt=(
            "Read 'C6_gdp.json' and 'C6_cpi.json'.\n"
            "1. Deflate GDP using first-period CPI base.\n"
            "2. Fit a simple linear regression: real_gdp = a + b*t, where t=0,1,2,...\n"
            "3. Forecast the next 4 quarters.\n"
            "Write 'answer.json' with:\n"
            '  - "slope": regression slope (float)\n'
            '  - "intercept": regression intercept (float)\n'
            '  - "forecast_next_4": list of 4 floats\n'
        ),
        input_data={
            "gdp": gdp, "cpi": cpi,
            "gdp_file": "C6_gdp.json", "cpi_file": "C6_cpi.json",
        },
        ground_truth={
            "slope": round(slope, 4),
            "intercept": round(intercept, 4),
            "forecast_next_4": next_4,
        },
        objective_fn_name="validate_numeric_close",
    ))

    return tasks


# ---------------------------------------------------------------------------
# Family D — GitHub Issues
# ---------------------------------------------------------------------------

def _family_D() -> List[DriftTask]:
    """Generate 6 GitHub issue analysis tasks with progressive drift."""
    issues = _synth_github_issues("pandas-dev/pandas", 200)

    # D1 ground truth — count by label
    label_counts: Dict[str, int] = {}
    for iss in issues:
        for lbl in iss["labels"]:
            label_counts[lbl["name"]] = label_counts.get(lbl["name"], 0) + 1
    top_label = max(label_counts, key=label_counts.get)  # type: ignore[arg-type]

    # D2 — sentiment: classify body as positive/negative
    pos_words = {"great", "thanks", "works", "awesome", "fixed", "love", "excellent"}
    neg_words = {"broken", "crash", "fail", "error", "regression", "slow", "blocker"}

    def _sentiment(body: str) -> str:
        words = set(body.lower().split())
        p = len(words & pos_words)
        n = len(words & neg_words)
        return "positive" if p >= n else "negative"

    sentiment_counts = {"positive": 0, "negative": 0}
    for iss in issues:
        sentiment_counts[_sentiment(iss["body"])] += 1

    # D3 — term extraction
    target_terms = ["core", "api", "cli", "db", "auth", "ui"]
    term_counts = {t: 0 for t in target_terms}
    for iss in issues:
        for t in target_terms:
            if t in iss["body"].lower():
                term_counts[t] += 1

    # D4 — issues by month
    month_counts: Dict[str, int] = {}
    for iss in issues:
        month = iss["created_at"][:7]
        month_counts[month] = month_counts.get(month, 0) + 1
    peak_month = max(month_counts, key=month_counts.get)  # type: ignore[arg-type]

    # D5 — contributor counts
    user_counts: Dict[str, int] = {}
    for iss in issues:
        u = iss["user"]["login"]
        user_counts[u] = user_counts.get(u, 0) + 1
    top_contributor = max(user_counts, key=user_counts.get)  # type: ignore[arg-type]

    tasks = []

    tasks.append(DriftTask(
        id="D1", name="D1_issue_label_counts", difficulty="easy",
        description="Count GitHub issues by label",
        validation_type="custom", category="github_issues",
        family="D", drift_level="none", drift_index=1,
        drift_description="Baseline: count issues by label",
        prompt=(
            "Read 'D1_issues.json' containing GitHub issues.\n"
            "Count how many issues have each label (issues can have multiple labels).\n"
            "Write 'answer.json' with:\n"
            '  - "label_counts": {"label_name": count, ...}\n'
            '  - "top_label": name of the most frequent label (str)\n'
            '  - "total_issues": total number of issues (int)\n'
        ),
        input_data={"issues": issues, "file": "D1_issues.json"},
        ground_truth={
            "label_counts": label_counts,
            "top_label": top_label,
            "total_issues": len(issues),
        },
        objective_fn_name="validate_json_keys",
    ))

    tasks.append(DriftTask(
        id="D2", name="D2_issue_sentiment", difficulty="easy",
        description="Classify issue sentiment (positive/negative)",
        validation_type="custom", category="github_issues",
        family="D", drift_level="minor", drift_index=2,
        prior_task_id="D1", oracle_skill_id="D1",
        drift_description="New requirement: classify issue body sentiment",
        prompt=(
            "Read 'D2_issues.json' containing GitHub issues.\n"
            "Classify each issue body as 'positive' or 'negative' using keyword matching:\n"
            f"  positive words: {sorted(pos_words)}\n"
            f"  negative words: {sorted(neg_words)}\n"
            "If positive keyword count >= negative keyword count, classify as 'positive'.\n"
            "Write 'answer.json' with:\n"
            '  - "sentiment_counts": {"positive": N, "negative": M}\n'
            '  - "total_issues": int\n'
        ),
        input_data={"issues": issues, "file": "D2_issues.json"},
        ground_truth={"sentiment_counts": sentiment_counts, "total_issues": len(issues)},
        objective_fn_name="validate_json_keys",
    ))

    tasks.append(DriftTask(
        id="D3", name="D3_term_extraction", difficulty="easy",
        description="Extract mentions of module terms from issue bodies",
        validation_type="custom", category="github_issues",
        family="D", drift_level="minor", drift_index=3,
        prior_task_id="D2", oracle_skill_id="D2",
        drift_description="New requirement: extract specific term mentions from bodies",
        prompt=(
            "Read 'D3_issues.json' containing GitHub issues.\n"
            f"Count how many issue bodies mention each of these terms: {target_terms}\n"
            "(case-insensitive substring match)\n"
            "Write 'answer.json' with:\n"
            '  - "term_counts": {"term": count, ...}\n'
        ),
        input_data={"issues": issues, "file": "D3_issues.json"},
        ground_truth={"term_counts": term_counts},
        objective_fn_name="validate_json_keys",
    ))

    tasks.append(DriftTask(
        id="D4", name="D4_issue_time_series", difficulty="medium",
        description="Issues over time — monthly counts and peak",
        validation_type="custom", category="github_issues",
        family="D", drift_level="moderate", drift_index=4,
        prior_task_id="D3", oracle_skill_id="D3",
        drift_description="Structural change: time-series analysis of issue creation dates",
        prompt=(
            "Read 'D4_issues.json' containing GitHub issues with 'created_at' timestamps.\n"
            "Count issues per month (YYYY-MM format).\n"
            "Write 'answer.json' with:\n"
            '  - "month_counts": {"YYYY-MM": count, ...}\n'
            '  - "peak_month": the month with the most issues (str)\n'
        ),
        input_data={"issues": issues, "file": "D4_issues.json"},
        ground_truth={"month_counts": month_counts, "peak_month": peak_month},
        objective_fn_name="validate_json_keys",
    ))

    tasks.append(DriftTask(
        id="D5", name="D5_contributor_analysis", difficulty="medium",
        description="Contributor network — top users and activity",
        validation_type="custom", category="github_issues",
        family="D", drift_level="moderate", drift_index=5,
        prior_task_id="D4", oracle_skill_id="D4",
        drift_description="New analysis: contributor activity counts",
        prompt=(
            "Read 'D5_issues.json' containing GitHub issues.\n"
            "Count how many issues each user created.\n"
            "Write 'answer.json' with:\n"
            '  - "user_counts": {"username": count, ...}\n'
            '  - "top_contributor": user who created the most issues (str)\n'
            '  - "unique_contributors": number of distinct users (int)\n'
        ),
        input_data={"issues": issues, "file": "D5_issues.json"},
        ground_truth={
            "user_counts": user_counts,
            "top_contributor": top_contributor,
            "unique_contributors": len(user_counts),
        },
        objective_fn_name="validate_json_keys",
    ))

    # D6 — major drift: combined analysis
    tasks.append(DriftTask(
        id="D6", name="D6_combined_issue_analysis", difficulty="hard",
        description="Combined: sentiment + contributor + time features",
        validation_type="custom", category="github_issues",
        family="D", drift_level="major", drift_index=6,
        prior_task_id="D5", oracle_skill_id="D5",
        drift_description="Major: combine sentiment, contributor, and time analysis in one output",
        prompt=(
            "Read 'D6_issues.json' containing GitHub issues.\n"
            "Produce a comprehensive analysis combining:\n"
            f"1. Sentiment counts (positive words: {sorted(pos_words)}, "
            f"negative words: {sorted(neg_words)})\n"
            "2. Top 3 contributors by issue count\n"
            "3. Peak month by issue creation\n"
            "Write 'answer.json' with:\n"
            '  - "sentiment_counts": {"positive": N, "negative": M}\n'
            '  - "top_3_contributors": [username1, username2, username3]\n'
            '  - "peak_month": "YYYY-MM"\n'
            '  - "total_issues": int\n'
        ),
        input_data={"issues": issues, "file": "D6_issues.json"},
        ground_truth={
            "sentiment_counts": sentiment_counts,
            "top_3_contributors": sorted(user_counts, key=user_counts.get, reverse=True)[:3],  # type: ignore[arg-type]
            "peak_month": peak_month,
            "total_issues": len(issues),
        },
        objective_fn_name="validate_json_keys",
    ))

    return tasks


# ---------------------------------------------------------------------------
# Family E — Fusion (Stock + GitHub Issues)
# ---------------------------------------------------------------------------

def _family_E(tickers: List[str]) -> List[DriftTask]:
    """Generate 6 fusion tasks combining stock data + GitHub issue sentiment."""
    ticker = tickers[0]
    rows = _synth_stock_rows(ticker, 120)
    issues = _synth_github_issues("pandas-dev/pandas", 200)

    closes = [r["Close"] for r in rows]
    returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
    avg_return = round(sum(returns) / len(returns), 6)

    pos_words = {"great", "thanks", "works", "awesome", "fixed", "love", "excellent"}
    neg_words = {"broken", "crash", "fail", "error", "regression", "slow", "blocker"}

    # Monthly sentiment score: (positive - negative) / total per month
    monthly_sentiment: Dict[str, float] = {}
    monthly_counts_sent: Dict[str, Dict[str, int]] = {}
    for iss in issues:
        month = iss["created_at"][:7]
        words = set(iss["body"].lower().split())
        p = len(words & pos_words)
        n = len(words & neg_words)
        if month not in monthly_counts_sent:
            monthly_counts_sent[month] = {"pos": 0, "neg": 0, "total": 0}
        monthly_counts_sent[month]["pos"] += p
        monthly_counts_sent[month]["neg"] += n
        monthly_counts_sent[month]["total"] += 1

    for m, c in monthly_counts_sent.items():
        monthly_sentiment[m] = round((c["pos"] - c["neg"]) / max(c["total"], 1), 4)

    # Monthly return
    monthly_return: Dict[str, float] = {}
    for i, r in enumerate(rows[1:], 1):
        m = r["Date"][:7]
        if m not in monthly_return:
            monthly_return[m] = 0.0
        monthly_return[m] += returns[i - 1] if i - 1 < len(returns) else 0.0

    # Correlation between sentiment and returns (matching months)
    common_months = sorted(set(monthly_sentiment) & set(monthly_return))
    if len(common_months) > 2:
        import math
        s_vals = [monthly_sentiment[m] for m in common_months]
        r_vals = [monthly_return[m] for m in common_months]
        n_cm = len(common_months)
        s_mean = sum(s_vals) / n_cm
        r_mean = sum(r_vals) / n_cm
        cov = sum((s_vals[i] - s_mean) * (r_vals[i] - r_mean) for i in range(n_cm)) / (n_cm - 1)
        std_s = math.sqrt(sum((s_vals[i] - s_mean)**2 for i in range(n_cm)) / (n_cm - 1))
        std_r = math.sqrt(sum((r_vals[i] - r_mean)**2 for i in range(n_cm)) / (n_cm - 1))
        sentiment_return_corr = round(cov / (std_s * std_r), 6) if (std_s and std_r) else 0.0
    else:
        sentiment_return_corr = 0.0

    tasks = []

    tasks.append(DriftTask(
        id="E1", name="E1_sentiment_return_correlation", difficulty="medium",
        description="Correlate monthly issue sentiment with stock returns",
        validation_type="custom", category="fusion",
        family="E", drift_level="none", drift_index=1,
        drift_description="Baseline: correlate monthly sentiment score with monthly stock return",
        prompt=(
            f"Read 'E1_stock.csv' ({ticker}) and 'E1_issues.json' (GitHub issues).\n"
            "1. Compute monthly aggregate stock returns from daily closes.\n"
            "2. Compute monthly sentiment score per issue:\n"
            f"   positive words: {sorted(pos_words)}, negative words: {sorted(neg_words)}\n"
            "   score = (pos_count - neg_count) / total_issues_in_month\n"
            "3. Compute Pearson correlation between monthly sentiment and monthly returns.\n"
            "Write 'answer.json' with:\n"
            '  - "sentiment_return_correlation": float\n'
            '  - "num_common_months": int\n'
        ),
        input_data={
            "rows": rows, "issues": issues,
            "stock_file": "E1_stock.csv", "issues_file": "E1_issues.json",
        },
        ground_truth={
            "sentiment_return_correlation": sentiment_return_corr,
            "num_common_months": len(common_months),
        },
        objective_fn_name="validate_numeric_close",
    ))

    # E2 — lag analysis: does sentiment lead returns by 1 month?
    if len(common_months) > 3:
        import math
        lagged_months = common_months[:-1]
        s_lag = [monthly_sentiment[m] for m in lagged_months]
        r_lead = [monthly_return[common_months[i+1]] for i in range(len(lagged_months))]
        n_lag = len(lagged_months)
        s_mean_l = sum(s_lag) / n_lag
        r_mean_l = sum(r_lead) / n_lag
        cov_l = sum((s_lag[i] - s_mean_l) * (r_lead[i] - r_mean_l) for i in range(n_lag)) / (n_lag - 1)
        std_sl = math.sqrt(sum((s_lag[i] - s_mean_l)**2 for i in range(n_lag)) / (n_lag - 1))
        std_rl = math.sqrt(sum((r_lead[i] - r_mean_l)**2 for i in range(n_lag)) / (n_lag - 1))
        lag_corr = round(cov_l / (std_sl * std_rl), 6) if (std_sl and std_rl) else 0.0
    else:
        lag_corr = 0.0

    tasks.append(DriftTask(
        id="E2", name="E2_lag_analysis", difficulty="medium",
        description="Lag analysis — does sentiment lead stock returns?",
        validation_type="custom", category="fusion",
        family="E", drift_level="minor", drift_index=2,
        prior_task_id="E1", oracle_skill_id="E1",
        drift_description="Add lag: correlate month-t sentiment with month-(t+1) returns",
        prompt=(
            f"Read 'E2_stock.csv' ({ticker}) and 'E2_issues.json'.\n"
            "1. Compute monthly sentiment scores and monthly returns as in E1.\n"
            "2. Compute lagged correlation: sentiment(month t) vs return(month t+1).\n"
            "Write 'answer.json' with:\n"
            '  - "lag_correlation": float\n'
            '  - "contemporaneous_correlation": float (same-month, as in E1)\n'
        ),
        input_data={
            "rows": rows, "issues": issues,
            "stock_file": "E2_stock.csv", "issues_file": "E2_issues.json",
        },
        ground_truth={
            "lag_correlation": lag_corr,
            "contemporaneous_correlation": sentiment_return_corr,
        },
        objective_fn_name="validate_numeric_close",
    ))

    # E3 — multi-company comparison
    ticker2 = tickers[1] if len(tickers) > 1 else tickers[0]
    rows2 = _synth_stock_rows(ticker2, 120)
    issues2 = _synth_github_issues("scikit-learn/scikit-learn", 200)
    closes2 = [r["Close"] for r in rows2]
    returns2 = [(closes2[i] - closes2[i-1]) / closes2[i-1] for i in range(1, len(closes2))]
    avg_return2 = round(sum(returns2) / len(returns2), 6)

    tasks.append(DriftTask(
        id="E3", name="E3_multi_company_comparison", difficulty="medium",
        description="Compare sentiment-return correlation for 2 companies",
        validation_type="custom", category="fusion",
        family="E", drift_level="minor", drift_index=3,
        prior_task_id="E2", oracle_skill_id="E2",
        drift_description="Scale to 2 companies: compare their sentiment-return correlations",
        prompt=(
            f"Read 'E3_stock1.csv' ({ticker}), 'E3_issues1.json' (repo A),\n"
            f"'E3_stock2.csv' ({ticker2}), 'E3_issues2.json' (repo B).\n"
            "For each company, compute monthly sentiment-return correlation.\n"
            "Write 'answer.json' with:\n"
            f'  - "correlation_{ticker}": float\n'
            f'  - "correlation_{ticker2}": float\n'
            '  - "stronger_signal": ticker with higher abs(correlation)\n'
        ),
        input_data={
            "rows1": rows, "rows2": rows2,
            "issues1": issues, "issues2": issues2,
            "files": ["E3_stock1.csv", "E3_issues1.json", "E3_stock2.csv", "E3_issues2.json"],
        },
        ground_truth={
            f"correlation_{ticker}": sentiment_return_corr,
            f"correlation_{ticker2}": sentiment_return_corr,
            "stronger_signal": ticker,
        },
        objective_fn_name="validate_json_keys",
    ))

    # E4 — sector-level aggregation
    tasks.append(DriftTask(
        id="E4", name="E4_sector_aggregation", difficulty="medium",
        description="Aggregate sentiment and returns at sector level",
        validation_type="custom", category="fusion",
        family="E", drift_level="moderate", drift_index=4,
        prior_task_id="E3", oracle_skill_id="E3",
        drift_description="Structural change: aggregate by sector instead of individual company",
        prompt=(
            f"Read 'E4_stock1.csv' ({ticker}), 'E4_stock2.csv' ({ticker2}),\n"
            "'E4_issues.json', and 'E4_sectors.json' (maps ticker->sector).\n"
            "1. Compute average daily return per stock.\n"
            "2. Compute overall sentiment score from issues.\n"
            "3. Group stocks by sector and compute sector average return.\n"
            "Write 'answer.json' with:\n"
            '  - "sector_returns": {"sector_name": avg_return, ...}\n'
            '  - "overall_sentiment_score": float\n'
        ),
        input_data={
            "rows1": rows, "rows2": rows2, "issues": issues,
            "sectors": {ticker: "Technology", ticker2: "Finance"},
            "files": ["E4_stock1.csv", "E4_stock2.csv", "E4_issues.json", "E4_sectors.json"],
        },
        ground_truth={
            "sector_returns": {"Technology": avg_return, "Finance": avg_return2},
            "overall_sentiment_score": round(
                sum(monthly_sentiment.values()) / max(len(monthly_sentiment), 1), 4),
        },
        objective_fn_name="validate_json_keys",
    ))

    # E5 — event detection
    # Find months with extreme sentiment
    if monthly_sentiment:
        sorted_months = sorted(monthly_sentiment.items(), key=lambda x: abs(x[1]), reverse=True)
        event_months = [m for m, _ in sorted_months[:3]]
    else:
        event_months = []

    tasks.append(DriftTask(
        id="E5", name="E5_event_detection", difficulty="hard",
        description="Detect event months from extreme sentiment",
        validation_type="custom", category="fusion",
        family="E", drift_level="moderate", drift_index=5,
        prior_task_id="E4", oracle_skill_id="E4",
        drift_description="New requirement: detect event months (extreme sentiment) and flag them",
        prompt=(
            f"Read 'E5_stock.csv' ({ticker}) and 'E5_issues.json'.\n"
            "1. Compute monthly sentiment scores.\n"
            "2. Identify the 3 months with the highest absolute sentiment score.\n"
            "3. For each event month, compute the stock return in that month.\n"
            "Write 'answer.json' with:\n"
            '  - "event_months": ["YYYY-MM", ...] (top 3 by abs sentiment)\n'
            '  - "event_returns": {"YYYY-MM": return, ...}\n'
        ),
        input_data={
            "rows": rows, "issues": issues,
            "stock_file": "E5_stock.csv", "issues_file": "E5_issues.json",
        },
        ground_truth={
            "event_months": event_months,
            "event_returns": {m: monthly_return.get(m, 0.0) for m in event_months},
        },
        objective_fn_name="validate_json_keys",
    ))

    # E6 — full predictive model (linear regression: sentiment -> next-month return)
    if len(common_months) > 3:
        import math
        x_vals = [monthly_sentiment[m] for m in common_months[:-1]]
        y_vals = [monthly_return[common_months[i+1]] for i in range(len(common_months) - 1)]
        n_f = len(x_vals)
        x_mean_f = sum(x_vals) / n_f
        y_mean_f = sum(y_vals) / n_f
        slope_f = sum((x_vals[i] - x_mean_f) * (y_vals[i] - y_mean_f)
                      for i in range(n_f)) / max(
            sum((x_vals[i] - x_mean_f)**2 for i in range(n_f)), 1e-12)
        intercept_f = y_mean_f - slope_f * x_mean_f
        last_sentiment = monthly_sentiment[common_months[-1]]
        predicted_return = round(intercept_f + slope_f * last_sentiment, 6)
    else:
        slope_f = 0.0
        intercept_f = 0.0
        predicted_return = 0.0

    tasks.append(DriftTask(
        id="E6", name="E6_predictive_model", difficulty="hard",
        description="Build predictive model: sentiment -> next month return",
        validation_type="custom", category="fusion",
        family="E", drift_level="major", drift_index=6,
        prior_task_id="E5", oracle_skill_id="E5",
        drift_description="Major: build linear prediction model from sentiment to future returns",
        prompt=(
            f"Read 'E6_stock.csv' ({ticker}) and 'E6_issues.json'.\n"
            "1. Compute monthly sentiment scores and monthly returns.\n"
            "2. Fit a linear regression: return(t+1) = a + b * sentiment(t)\n"
            "3. Use the model to predict the return for the month AFTER the last data month.\n"
            "Write 'answer.json' with:\n"
            '  - "slope": regression coefficient (float)\n'
            '  - "intercept": regression intercept (float)\n'
            '  - "predicted_next_return": float\n'
        ),
        input_data={
            "rows": rows, "issues": issues,
            "stock_file": "E6_stock.csv", "issues_file": "E6_issues.json",
        },
        ground_truth={
            "slope": round(slope_f, 6),
            "intercept": round(intercept_f, 6),
            "predicted_next_return": predicted_return,
        },
        objective_fn_name="validate_numeric_close",
    ))

    return tasks


# ---------------------------------------------------------------------------
# Family F — Explicit Composition (5 tasks)
# ---------------------------------------------------------------------------

def _family_F(tickers: List[str]) -> List[DriftTask]:
    """
    Generate 5 explicit composition tasks requiring skills from multiple families.
    
    F1: B + C — Portfolio risk + economic indicator correlation
    F2: A + D — Stock report + issue sentiment summary
    F3: A + B — Stock returns + momentum + risk metrics
    F4: D + C — Issue labels by economic quarter
    F5: A + B + D — Full: stock, risk, sentiment, formatted report
    """
    import math
    
    t1, t2 = tickers[0], tickers[1] if len(tickers) > 1 else tickers[0]
    rows1 = _synth_stock_rows(t1, 120)
    rows2 = _synth_stock_rows(t2, 120)
    issues = _synth_github_issues("pandas-dev/pandas", 200)
    gdp = _synth_economic_series("GDP", 60)
    cpi = _synth_economic_series("CPI", 60)
    
    # Ground truths
    closes1 = [r["Close"] for r in rows1]
    returns1 = [(closes1[i] - closes1[i-1]) / closes1[i-1] for i in range(1, len(closes1))]
    closes2 = [r["Close"] for r in rows2]
    returns2 = [(closes2[i] - closes2[i-1]) / closes2[i-1] for i in range(1, len(closes2))]
    
    # F1: Portfolio VaR for two stocks + correlate with GDP growth
    port_rets = [0.5 * returns1[i] + 0.5 * returns2[i] for i in range(min(len(returns1), len(returns2)))]
    var_95 = round(sorted(port_rets)[max(0, int(len(port_rets) * 0.05) - 1)], 6)
    gdp_vals = [r["value"] for r in gdp]
    gdp_growth = [(gdp_vals[i] - gdp_vals[i-1]) / gdp_vals[i-1] for i in range(1, min(20, len(gdp_vals)))]
    n_corr = min(len(port_rets[:20]), len(gdp_growth))
    if n_corr > 2:
        pr_mean = sum(port_rets[:n_corr]) / n_corr
        gg_mean = sum(gdp_growth) / len(gdp_growth)
        cov = sum((port_rets[i] - pr_mean) * (gdp_growth[i] - gg_mean) for i in range(n_corr)) / (n_corr - 1)
        std_pr = math.sqrt(sum((port_rets[i] - pr_mean)**2 for i in range(n_corr)) / (n_corr - 1))
        std_gg = math.sqrt(sum((gdp_growth[i] - gg_mean)**2 for i in range(n_corr)) / (n_corr - 1))
        corr_gdp = round(cov / (std_pr * std_gg), 6) if (std_pr and std_gg) else 0.0
    else:
        corr_gdp = 0.0
    
    # F2/F5: Stock report + sentiment summary
    pos_words = {"great", "thanks", "works", "awesome", "fixed", "love", "excellent"}
    neg_words = {"broken", "crash", "fail", "error", "regression", "slow", "blocker"}
    pos_count = 0
    for iss in issues:
        words = set(iss["body"].lower().split())
        p, n = len(words & pos_words), len(words & neg_words)
        if p >= n:
            pos_count += 1
    sentiment_summary = {"positive": pos_count, "negative": len(issues) - pos_count}
    avg_ret = round(sum(returns1) / len(returns1), 6)
    
    # F3: Momentum (10-day) + Sharpe + VaR
    momentum_10 = sum(returns1[-10:]) if len(returns1) >= 10 else sum(returns1)
    std_r = math.sqrt(sum((r - sum(returns1)/len(returns1))**2 for r in returns1) / (len(returns1)-1)) if len(returns1) > 1 else 0.01
    sharpe = round(sum(returns1)/len(returns1) / std_r * math.sqrt(252), 6) if std_r else 0.0
    var_single = round(sorted(returns1)[max(0, int(len(returns1)*0.05)-1)], 6)
    
    # F4: Issues by label, aggregated by economic quarter
    label_counts: Dict[str, int] = {}
    for iss in issues:
        for lbl in iss["labels"]:
            label_counts[lbl["name"]] = label_counts.get(lbl["name"], 0) + 1
    # Map issue created_at to quarter (simplified: use first 4 months as Q1)
    quarter_issues: Dict[str, int] = {}
    for iss in issues:
        m = iss["created_at"][5:7]
        q = "Q1" if m in ("01","02","03") else "Q2" if m in ("04","05","06") else "Q3" if m in ("07","08","09") else "Q4"
        quarter_issues[q] = quarter_issues.get(q, 0) + 1
    peak_q = max(quarter_issues, key=quarter_issues.get)  # type: ignore[arg-type]
    
    # F5: Combined metrics
    top_label = max(label_counts, key=label_counts.get)  # type: ignore[arg-type]
    
    tasks = []
    
    tasks.append(DriftTask(
        id="F1", name="F1_portfolio_economic_correlation", difficulty="hard",
        description="Portfolio VaR + GDP growth correlation (B + C)",
        validation_type="custom", category="composition",
        family="F", drift_level="none", drift_index=1, drift_type="none",
        prior_task_id=None, oracle_skill_id=None,
        drift_description="Composition: portfolio risk (B) + economic indicator (C)",
        prompt=(
            f"Read 'F1_stock1.csv' ({t1}), 'F1_stock2.csv' ({t2}), 'F1_gdp.json'.\n"
            "1. Form equal-weight portfolio, compute 95%% VaR.\n"
            "2. Compute GDP growth (period-over-period % change).\n"
            "3. Correlate first 20 portfolio returns with first 20 GDP growth values.\n"
            "Write 'answer.json' with:\n"
            '  - "portfolio_var_95": float\n'
            '  - "portfolio_gdp_correlation": float\n'
            '  - "num_observations": int\n'
        ),
        input_data={
            "rows1": rows1, "rows2": rows2, "gdp": gdp,
            "files": ["F1_stock1.csv", "F1_stock2.csv", "F1_gdp.json"],
        },
        ground_truth={
            "portfolio_var_95": var_95,
            "portfolio_gdp_correlation": corr_gdp,
            "num_observations": n_corr,
        },
        objective_fn_name="validate_numeric_close",
    ))
    
    tasks.append(DriftTask(
        id="F2", name="F2_stock_report_sentiment", difficulty="medium",
        description="Stock report + issue sentiment (A + D)",
        validation_type="custom", category="composition",
        family="F", drift_level="none", drift_index=2, drift_type="none",
        prior_task_id=None, oracle_skill_id=None,
        drift_description="Composition: stock analysis (A) + GitHub issues (D)",
        prompt=(
            f"Read 'F2_stock.csv' ({t1}) and 'F2_issues.json'.\n"
            "1. Calculate average daily return from stock.\n"
            "2. Classify each issue: positive if body has more positive keywords than negative.\n"
            "   Positive: great, thanks, works, awesome, fixed, love, excellent\n"
            "   Negative: broken, crash, fail, error, regression, slow, blocker\n"
            "Write 'answer.json' with:\n"
            '  - "avg_daily_return": float\n'
            '  - "sentiment_counts": {"positive": N, "negative": M}\n'
            '  - "total_issues": int\n'
        ),
        input_data={
            "rows": rows1, "issues": issues,
            "stock_file": "F2_stock.csv", "issues_file": "F2_issues.json",
        },
        ground_truth={
            "avg_daily_return": avg_ret,
            "sentiment_counts": sentiment_summary,
            "total_issues": len(issues),
        },
        objective_fn_name="validate_json_keys",
    ))
    
    tasks.append(DriftTask(
        id="F3", name="F3_momentum_risk_metrics", difficulty="medium",
        description="Momentum + Sharpe + VaR (A + B)",
        validation_type="custom", category="composition",
        family="F", drift_level="none", drift_index=3, drift_type="none",
        prior_task_id=None, oracle_skill_id=None,
        drift_description="Composition: stock analysis (A) + portfolio risk (B)",
        prompt=(
            f"Read 'F3_stock.csv' ({t1}).\n"
            "1. Compute 10-day momentum (sum of last 10 daily returns).\n"
            "2. Compute annualized Sharpe ratio (risk-free=0, sqrt(252)).\n"
            "3. Compute 95%% VaR.\n"
            "Write 'answer.json' with:\n"
            '  - "momentum_10d": float\n'
            '  - "sharpe_ratio": float\n'
            '  - "var_95": float\n'
        ),
        input_data={"rows": rows1, "file": "F3_stock.csv", "ticker": t1},
        ground_truth={
            "momentum_10d": round(momentum_10, 6),
            "sharpe_ratio": sharpe,
            "var_95": var_single,
        },
        objective_fn_name="validate_numeric_close",
    ))
    
    tasks.append(DriftTask(
        id="F4", name="F4_issues_by_quarter", difficulty="medium",
        description="Issue labels aggregated by economic quarter (D + C)",
        validation_type="custom", category="composition",
        family="F", drift_level="none", drift_index=4, drift_type="none",
        prior_task_id=None, oracle_skill_id=None,
        drift_description="Composition: GitHub issues (D) + economic period (C)",
        prompt=(
            "Read 'F4_issues.json' with created_at timestamps.\n"
            "Map each issue to a quarter: Jan-Mar=Q1, Apr-Jun=Q2, Jul-Sep=Q3, Oct-Dec=Q4.\n"
            "Count issues per quarter.\n"
            "Write 'answer.json' with:\n"
            '  - "quarter_counts": {"Q1": N, "Q2": N, "Q3": N, "Q4": N}\n'
            '  - "peak_quarter": "Q1"|"Q2"|"Q3"|"Q4"\n'
            '  - "total_issues": int\n'
        ),
        input_data={"issues": issues, "file": "F4_issues.json"},
        ground_truth={
            "quarter_counts": quarter_issues,
            "peak_quarter": peak_q,
            "total_issues": len(issues),
        },
        objective_fn_name="validate_json_keys",
    ))
    
    tasks.append(DriftTask(
        id="F5", name="F5_full_composition_report", difficulty="hard",
        description="Stock + risk + sentiment + formatted report (A + B + D)",
        validation_type="custom", category="composition",
        family="F", drift_level="none", drift_index=5, drift_type="none",
        prior_task_id=None, oracle_skill_id=None,
        drift_description="Full composition: A + B + D skills combined",
        prompt=(
            f"Read 'F5_stock.csv' ({t1}) and 'F5_issues.json'.\n"
            "Produce a compliance-style report with:\n"
            "1. Average daily return (from stock)\n"
            "2. 95%% VaR (from stock returns)\n"
            "3. Sharpe ratio (annualized)\n"
            "4. Sentiment summary: count positive vs negative issues (keywords: positive=great,thanks,works,awesome,fixed,love,excellent; negative=broken,crash,fail,error,regression,slow,blocker)\n"
            "5. Top issue label\n"
            "Write 'answer.json' with:\n"
            '  - "avg_daily_return": float\n'
            '  - "var_95": float\n'
            '  - "sharpe_ratio": float\n'
            '  - "sentiment_positive": int\n'
            '  - "sentiment_negative": int\n'
            '  - "top_label": str\n'
            '  - "total_issues": int\n'
        ),
        input_data={
            "rows": rows1, "issues": issues,
            "stock_file": "F5_stock.csv", "issues_file": "F5_issues.json",
        },
        ground_truth={
            "avg_daily_return": avg_ret,
            "var_95": var_single,
            "sharpe_ratio": sharpe,
            "sentiment_positive": sentiment_summary["positive"],
            "sentiment_negative": sentiment_summary["negative"],
            "top_label": top_label,
            "total_issues": len(issues),
        },
        objective_fn_name="validate_json_keys",
    ))
    
    return tasks


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------

class DriftTaskGenerator:
    """
    Generates 35 ConceptDrift tasks (5 families × 6 drift levels + 5 composition).

    Data is synthetic by default. Set source="ds1000" to use real DS-1000 tasks
    for family D (requires: pip install datasets).
    """

    def __init__(
        self,
        stock_dir: Optional[str] = None,
        descriptions_csv: Optional[str] = None,
        output_dir: Optional[str] = None,
        seed: int = RANDOM_SEED,
        source: str = "synthetic",
    ):
        self.seed = seed
        self.stock_dir = Path(stock_dir) if stock_dir else None
        self.descriptions_csv = Path(descriptions_csv) if descriptions_csv else None
        self.output_dir = Path(output_dir) if output_dir else Path("benchmarks/conceptdrift/data")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.source = source or "synthetic"
        self._tickers = ["AAPL", "MSFT", "AMZN", "NVDA", "TSLA"]

    def generate(self) -> List[DriftTask]:
        """Generate all 30 tasks across 5 families."""
        random.seed(self.seed)
        all_tasks: List[DriftTask] = []
        data_dir = self.output_dir

        if self.source == "bigcode":
            logger.info("Generating Family A: BigCodeBench (real Python tasks)...")
            from .families.bigcode import BigCodeBenchLoader
            loader = BigCodeBenchLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        elif self.source == "humaneval":
            logger.info("Generating Family A: HumanEval (real Python tasks)...")
            from .families.humaneval import HumanEvalLoader
            loader = HumanEvalLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        else:
            logger.info("Generating Family A: Stock Analysis...")
            all_tasks.extend(_family_A(self._tickers, self.output_dir))

        logger.info("Generating Family B: Portfolio Risk...")
        all_tasks.extend(_family_B(self._tickers))

        if self.source == "spider":
            logger.info("Generating Family C: Spider (real SQL tasks)...")
            from .families.spider import SpiderFamilyLoader
            loader = SpiderFamilyLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        elif self.source == "spider2":
            logger.info("Generating Family C: Spider 2.0 / BIRD (real SQL tasks)...")
            from .families.spider2 import Spider2FamilyLoader
            loader = Spider2FamilyLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        elif self.source == "spider2_hard":
            logger.info("Generating Family C: Spider 2.0 Hard / BIRD dev (moderate/challenging only)...")
            from .families.spider2_hard import Spider2HardLoader
            loader = Spider2HardLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        elif self.source == "spider2_sameschema":
            logger.info("Generating Family C: Spider 2.0 Same-Schema (controlled drift)...")
            from .families.spider2_sameschema import Spider2SameSchemaLoader
            loader = Spider2SameSchemaLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        else:
            logger.info("Generating Family C: Economic Indicators...")
            all_tasks.extend(_family_C())

        if self.source == "ds1000":
            logger.info("Generating Family D: DS-1000 (real Pandas tasks)...")
            from .families.ds1000 import DS1000FamilyLoader
            loader = DS1000FamilyLoader()
            all_tasks.extend(loader.load_tasks(data_dir, seed=self.seed, limit=6))
        else:
            logger.info("Generating Family D: GitHub Issues...")
            all_tasks.extend(_family_D())

        logger.info("Generating Family E: Fusion...")
        all_tasks.extend(_family_E(self._tickers))

        logger.info("Generating Family F: Composition...")
        all_tasks.extend(_family_F(self._tickers))

        # Tag each task with drift_type from taxonomy and ensure backend support
        for t in all_tasks:
            t.drift_type = DRIFT_TYPE_BY_INDEX.get(t.drift_index, "none")
            if not t.supported_backends:
                t.supported_backends = ["opensandbox", "subprocess"]

        logger.info(f"Generated {len(all_tasks)} tasks across 6 families")
        return all_tasks

    def write_task_files(self, tasks: List[DriftTask]) -> None:
        """Write input data files to output_dir for each task."""
        for task in tasks:
            if not task.input_data:
                continue
            self._write_input_files(task)
        logger.info(f"Wrote input files to {self.output_dir}")

    def _write_input_files(self, task: DriftTask) -> None:
        """Write the input data files for a single task."""
        data = task.input_data or {}

        # Write stock CSV files
        for key in ["rows", "rows1", "rows2", "spy_rows"]:
            if key in data:
                file_keys = {
                    "rows": "file", "rows1": "file1",
                    "rows2": "file2", "spy_rows": "spy_file",
                }
                fname = data.get(file_keys.get(key, "file"), f"{task.id}_{key}.csv")
                self._write_csv(data[key], self.output_dir / fname)

        # Multi-stock files (B4-B6)
        if "tickers" in data and "files" in data:
            for i, ticker in enumerate(data["tickers"]):
                fname = data["files"][i]
                rows = _synth_stock_rows(ticker, 120)
                self._write_csv(rows, self.output_dir / fname)

        # JSON data (economic, issues, descriptions)
        for key in ["gdp", "cpi", "consumption", "investment", "issues",
                     "issues1", "issues2", "descriptions", "sectors"]:
            if key in data:
                file_key = f"{key}_file"
                if file_key in data:
                    fname = data[file_key]
                elif key == "issues":
                    fname = data.get("file", data.get("issues_file", f"{task.id}_{key}.json"))
                elif key == "descriptions":
                    fname = data.get("descriptions_file", f"{task.id}_descriptions.json")
                else:
                    fname = f"{task.id}_{key}.json"
                path = self.output_dir / fname
                with open(path, "w") as f:
                    json.dump(data[key], f, indent=2)

        # E-family: write stock as CSV and issues as JSON
        if "stock_file" in data and "rows" in data:
            self._write_csv(data["rows"], self.output_dir / data["stock_file"])
        if "issues_file" in data and "issues" in data:
            with open(self.output_dir / data["issues_file"], "w") as f:
                json.dump(data["issues"], f, indent=2)

        # Multi-file E-family and F-family
        if "files" in data and isinstance(data["files"], list):
            for fname in data["files"]:
                if fname.endswith(".csv"):
                    key_map = {"stock1": "rows1", "stock2": "rows2", "stock": "rows"}
                    for pat, rkey in key_map.items():
                        if pat in fname and rkey in data:
                            self._write_csv(data[rkey], self.output_dir / fname)
                            break
                elif fname.endswith(".json"):
                    written = False
                    for jkey in ["issues", "issues1", "issues2", "sectors", "gdp"]:
                        if jkey in fname.lower() and jkey in data:
                            with open(self.output_dir / fname, "w") as f:
                                json.dump(data[jkey], f, indent=2)
                            written = True
                            break
                    if not written and "sectors" in fname and "sectors" in data:
                        with open(self.output_dir / fname, "w") as f:
                            json.dump(data["sectors"], f, indent=2)

    @staticmethod
    def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
        if not rows:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def write_manifest(self, tasks: List[DriftTask]) -> Path:
        """Write a tasks manifest JSON for the runner."""
        manifest = []
        for t in tasks:
            entry = {
                "id": t.id,
                "name": t.name,
                "family": t.family,
                "drift_level": t.drift_level,
                "drift_type": getattr(t, "drift_type", "none"),
                "drift_index": t.drift_index,
                "prior_task_id": t.prior_task_id,
                "oracle_skill_id": t.oracle_skill_id,
                "drift_description": t.drift_description,
                "difficulty": t.difficulty,
                "category": t.category,
                "prompt": t.prompt,
                "validation_type": t.validation_type,
                "objective_fn_name": t.objective_fn_name,
            }
            manifest.append(entry)

        manifest_path = self.output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Wrote manifest to {manifest_path}")
        return manifest_path


# ---------------------------------------------------------------------------
# Validation dispatch — used by the runner
# ---------------------------------------------------------------------------

VALIDATORS = {
    "validate_numeric_close": _validate_numeric_close,
    "validate_json_keys": _validate_json_keys,
    "ds1000_execution": _validate_ds1000_execution,
    "bigcode_execution": _validate_bigcode_execution,
    "humaneval_execution": _validate_humaneval,
    "spider_sql": _validate_spider_sql,
    "spider2_sql": _validate_spider2_sql,
}


def get_validator(name: str) -> Callable:
    """Look up a validator function by name."""
    if name not in VALIDATORS:
        raise ValueError(f"Unknown validator: {name}. Available: {list(VALIDATORS.keys())}")
    return VALIDATORS[name]
