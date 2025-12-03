import asyncio
import logging
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import aiohttp
import aiofiles
import os
import csv
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Database setup
DB_PATH = "results.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  url TEXT,
                  status_code INTEGER,
                  error TEXT,
                  timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

# User Agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.106 Safari/537.36"
]

import random

# Global state (simple in-memory for this tool)
class JobState:
    is_running = False
    total_urls = 0
    checked_count = 0
    error_count = 0
    start_time = None
    urls_to_check = []
    recent_errors = [] # List of strings
    
state = JobState()

class CheckConfig(BaseModel):
    concurrency: int = 50
    requests_per_second: int = 100
    timeout: int = 10
    resume: bool = False
    retries: int = 1

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    # Deduplicate URLs
    urls = list(set([line.strip() for line in text.splitlines() if line.strip()]))
    state.urls_to_check = urls
    state.total_urls = len(urls)
    state.checked_count = 0
    state.error_count = 0
    state.recent_errors = []
    return {"count": len(urls), "message": "File uploaded successfully (duplicates removed)"}

async def worker(sem, rate_limiter, session, url, timeout, retries):
    async with sem:
        for attempt in range(retries + 1):
            # Simple rate limiting
            await rate_limiter.acquire()
            
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            
            try:
                async with session.get(url, timeout=timeout, ssl=False, headers=headers) as response:
                    status = response.status
                    if status >= 400:
                        error = response.reason
                    else:
                        error = None
                        break # Success (or at least got a response), stop retrying
            except Exception as e:
                status = 0
                error = str(e)
                # If it's the last attempt, we keep the error. Otherwise continue to retry.
                if attempt < retries:
                    continue
        
        # Update state
        state.checked_count += 1
        if status == 0 or status >= 400:
            state.error_count += 1
            # Add to recent errors (keep last 50)
            err_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {url} -> {status} ({error})"
            state.recent_errors.append(err_msg)
            if len(state.recent_errors) > 50:
                state.recent_errors.pop(0)
            
        # Save to DB (batching would be better for 1M+, but keeping simple for now)
        # In a real high-perf scenario, we'd push to a queue and have a separate writer
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO results (url, status_code, error, timestamp) VALUES (?, ?, ?, ?)",
                      (url, status, error, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"DB Error: {e}")

class RateLimiter:
    def __init__(self, rate_limit):
        self.rate_limit = rate_limit
        self.tokens = rate_limit
        self.last_update = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = datetime.now()
            elapsed = (now - self.last_update).total_seconds()
            self.tokens = min(self.rate_limit, self.tokens + elapsed * self.rate_limit)
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate_limit
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= 1

async def run_checks(config: CheckConfig):
    state.is_running = True
    state.start_time = datetime.now()
    
    checked_urls = set()
    if config.resume:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT url FROM results")
        checked_urls = set(row[0] for row in c.fetchall())
        conn.close()
        # Update checked count based on DB
        state.checked_count = len(checked_urls)
        # Recalculate errors if needed, but for now we trust the DB count
        # (Error count might be desynced if we restart server, but that's acceptable for this scope)
    
    sem = asyncio.Semaphore(config.concurrency)
    rate_limiter = RateLimiter(config.requests_per_second)
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for url in state.urls_to_check:
            if not state.is_running:
                break
            if config.resume and url in checked_urls:
                continue
                
            task = asyncio.create_task(worker(sem, rate_limiter, session, url, config.timeout, config.retries))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks)
    
    state.is_running = False

@app.post("/api/start")
async def start_check(config: CheckConfig, background_tasks: BackgroundTasks):
    if state.is_running:
        raise HTTPException(status_code=400, detail="Job already running")
    if not state.urls_to_check:
        raise HTTPException(status_code=400, detail="No URLs uploaded")
    
    if not config.resume:
        # Clear previous results only if NOT resuming
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM results")
        conn.commit()
        conn.close()
        
        state.checked_count = 0
        state.error_count = 0
        state.recent_errors = []
    
    background_tasks.add_task(run_checks, config)
    return {"message": "Started"}

@app.post("/api/stop")
async def stop_check():
    state.is_running = False
    return {"message": "Stopping..."}

@app.get("/api/status")
async def get_status():
    return {
        "running": state.is_running,
        "total": state.total_urls,
        "checked": state.checked_count,
        "errors": state.error_count,
        "recent_errors": state.recent_errors,
        "start_time": state.start_time.isoformat() if state.start_time else None
    }

@app.get("/api/results")
async def get_results():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT url, status_code, error, timestamp FROM results")
    rows = c.fetchall()
    conn.close()
    
    filename = "results.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["url", "status_code", "error", "timestamp"])
        writer.writerows(rows)
        
    return FileResponse(path=filename, filename="results.csv", media_type='text/csv')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
