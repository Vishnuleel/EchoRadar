"""`python -m api` - start the NEXUS API (and the built frontend, if web/dist exists) on port 8000."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host=os.getenv("NEXUS_HOST", "127.0.0.1"), port=int(os.getenv("NEXUS_PORT", "8000")))
