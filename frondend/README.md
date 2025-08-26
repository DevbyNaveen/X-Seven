# X‑SevenAI Frontend (WhatsApp‑like)

A minimal, static chat UI to talk to your backend AI via WebSocket or HTTP.

## Features

- WhatsApp‑like layout and dark theme
- WebSocket to `/api/v1/chat/ws/{session_id}` with HTTP fallback to `POST /api/v1/chat/message`
- Optional Dedicated mode (enter Business ID) to use `/api/v1/dedicated-chat/...`
- Quick action buttons supported from `suggested_actions`

## Start (dev)

1. Ensure backend is running locally on `http://localhost:8000` (FastAPI).
2. Serve this folder on a local web server to satisfy CORS/origin.

Examples:

- Python
  ```bash
  python3 -m http.server 3000 --directory frondedn
  ```
  Then open http://localhost:3000 in your browser.

- Node (if you have npx)
  ```bash
  npx serve -p 3000 frondedn
  ```

> Opening `index.html` directly from the filesystem (file://) may work, but a local server is recommended for CORS and WebSocket origin handling.

## Configuration

- The app assumes API base `http://localhost:8000/api/v1`. If your backend runs elsewhere, edit `API_BASE` at the top of `frondedn/app.js`.

## Endpoints used

- Universal chat
  - HTTP: `POST /api/v1/chat/message`
  - WS:   `GET  /api/v1/chat/ws/{session_id}`
- Dedicated chat (enable the "Dedicated" toggle and enter Business ID)
  - HTTP: `POST /api/v1/dedicated-chat/message/{business_id}`
  - WS:   `GET  /api/v1/dedicated-chat/ws/{business_id}/{session_id}`

## Notes

- Session ID is persisted in `localStorage` (`x7_chat_session_id`). Use your browser devtools to clear it and start fresh.
- Suggested actions can be strings or objects with `{ id, title }`. Clicking sends the `title` as the message.
- If WS disconnects, you can click Connect to reconnect.
