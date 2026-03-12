"""Run the V-Rēķini web application (development only).

For production, use the systemd service which runs uvicorn directly.
Do NOT run this file on the production server.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
