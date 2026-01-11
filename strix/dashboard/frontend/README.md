# Strix Dashboard Frontend

Advanced Next.js dashboard for real-time Strix security scan monitoring.

## Setup

```bash
# Install dependencies
npm install

# Development mode (runs on port 3000)
npm run dev

# Build for production (outputs to out/)
npm run build

# The built files will be served by the Python backend at strix/dashboard/web_server.py
```

## Features

- Real-time monitoring via Server-Sent Events (SSE)
- Historical data visualization
- Interactive charts and analytics
- Advanced filtering and search
- Export functionality (JSON, CSV, PDF)
- Professional UI with shadcn/ui components

## Development

The dashboard is built with:
- Next.js 14+ (App Router)
- TypeScript
- shadcn/ui components
- Tailwind CSS
- Recharts for data visualization

## Building for Production

After building, the static files in `out/` are served by the Python HTTP server. The server automatically detects and serves the Next.js build output.