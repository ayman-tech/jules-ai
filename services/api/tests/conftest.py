import os
import tempfile

os.environ["APP_ENV"] = "development"
os.environ["AUTH_MODE"] = "development"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp(prefix='jules-ai-tests-')}/jules-ai-test.db"
os.environ["LOCAL_UPLOAD_DIR"] = tempfile.mkdtemp(prefix="jules-ai-test-uploads-")
os.environ["LOG_DIR"] = tempfile.mkdtemp(prefix="jules-ai-test-logs-")
