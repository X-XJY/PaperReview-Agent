import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.getenv('DATA_DIR', './data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
MAX_FILES = min(8, max(1, int(os.getenv('MAX_BATCH_FILES', '8'))))
MAX_BYTES = int(os.getenv('MAX_FILE_MB', '30')) * 1024 * 1024
MAX_PAGES = int(os.getenv('MAX_PDF_PAGES', '50'))

def configured():
    return all(os.getenv(k) for k in ('MINERU_API_KEY', 'LLM_API_KEY', 'LLM_MODEL'))
