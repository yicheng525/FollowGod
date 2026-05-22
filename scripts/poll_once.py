import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.service import PollService
from app.storage import FilingStore


async def main() -> None:
    settings = get_settings()
    store = FilingStore(settings.database_path)
    service = PollService(settings, store)
    result = await service.poll_once()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
