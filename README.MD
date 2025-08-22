🚀 X-SevenAI - Universal Business Automation Platform
📖 Overview
X-SevenAI is a revolutionary universal business automation platform that transforms any appointment-based or service business with AI-powered customer interaction. The system supports 5 major business categories and multiple communication channels including QR codes, voice calls, WhatsApp, and web interfaces.

🎯 NEW: Top 5 Business Categories Support
🥇 1. FOOD & HOSPITALITY
Target: Restaurants, cafes, bars, bakeries, food trucks
Features: QR ordering, table management, multi-language menus, kitchen display
Pricing: €50-100/month | Revenue Impact: 20-30% increase
🥈 2. BEAUTY & PERSONAL CARE
Target: Hair salons, nail salons, beauty salons, barber shops, spas
Features: Appointment scheduling, stylist management, deposit handling, reminders
Pricing: €75-150/month | Revenue Impact: €400+ daily from captured calls
🥉 3. AUTOMOTIVE SERVICES
Target: Auto repair shops, car washes, tire centers, oil change services
Features: Service bay management, parts coordination, progress updates, emergency service
Pricing: €100-200/month | Revenue Impact: €5,000+ monthly from uninterrupted work
🏅 4. HEALTH & MEDICAL
Target: Dental clinics, physiotherapy, general practice, veterinary clinics
Features: Insurance verification, emergency appointments, medical history, HIPAA compliance
Pricing: €150-300/month | Revenue Impact: €4,000+ monthly from improved efficiency
🎖️ 5. LOCAL SERVICES
Target: Cleaning services, pet grooming, tutoring, home repair, landscaping
Features: Mobile service coordination, location-based scheduling, recurring services
Pricing: €75-125/month | Revenue Impact: 30% efficiency gain
Total Addressable Market: 5+ Million Small Businesses

🌟 Key Features
Universal Business Support: 5 major business categories with specialized automation
Multi-Channel Support: QR codes, voice calls, WhatsApp, web interface
Natural Language Processing: Understands customer intent in multiple languages
Multi-Tenant Architecture: One system serves multiple businesses
Real-Time Order Management: Live order tracking and status updates
AI-Powered Customer Service: Intelligent conversation handling
Comprehensive Analytics: Business intelligence and reporting
Voice Integration: Text-to-speech and speech-to-text capabilities
Appointment Scheduling: Advanced booking system with service providers
Payment Processing: Integrated payment solutions
Category-Specific Templates: Instant business setup with industry-specific features

## Simplified AI Backend - Usage

The simplified AI backend exposes lightweight chat and business endpoints.

### REST: Chat
- Endpoint: `POST /api/v1/chat/message`
- Body:
```json
{
  "message": "Hello, can I book a table?",
  "session_id": "optional-session-id",
  "context": { "business_id": 1 }
}
```
- Response:
```json
{
  "message": "...assistant reply...",
  "session_id": "...",
  "success": true,
  "metadata": { }
}
```

### WebSocket: Chat
- URL: `ws://localhost:8000/api/v1/chat/ws/{session_id}`
- Send JSON messages like:
```json
{ "message": "Show me the menu", "context": { "business_id": 1 } }
```
- Server emits events:
  - `{ "type": "connected", "message": "..." }`
  - `{ "type": "typing", "typing": true|false }`
  - `{ "type": "message_start" }`
  - `{ "type": "message_chunk", "character": "a", "position": 0 }`
  - `{ "type": "message_complete", "full_message": "..." }`

### Business Endpoints
- List active businesses: `GET /api/v1/businesses`
- Get business menu: `GET /api/v1/businesses/{business_id}/menu`

## Environment Configuration

Create a `.env` file (see `.env.example`) with:

- `GROQ_API_KEY`: Required for real AI responses via Groq
- `GROQ_MODEL` (optional): Defaults to `llama-3.1-8b-instant`
- `DATABASE_URL`: SQLite default is set; customize as needed
- `API_URL`: e.g., `http://localhost:8000`

Example (bash):
```bash
export GROQ_API_KEY="sk_..."
export GROQ_MODEL="llama-3.1-8b-instant"
uvicorn app.main:app --reload
```

If `GROQ_API_KEY` is not set, the chat endpoint will return a helpful fallback message indicating AI is not configured.