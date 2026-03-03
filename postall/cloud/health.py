"""
Health Check HTTP Server for PostAll Cloud

Provides HTTP endpoints for Docker/Kubernetes health probes:
- GET /health  - Full health status with stats
- GET /ready   - Readiness probe (can accept traffic)
- GET /live    - Liveness probe (process is alive)
- GET /media/* - Static file serving for generated content (images for Instagram)
"""

import asyncio
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Dict, Any, Optional, Callable
from urllib.parse import unquote

from postall.config import TIMEZONE
from zoneinfo import ZoneInfo


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health endpoints."""

    # Class-level references (set by HealthServer)
    start_time: datetime = None
    stats_callback: Callable = None
    publishers_callback: Callable = None
    media_server = None  # MediaServer instance for static file serving

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def _send_file(self, content: bytes, mime_type: str, filename: str = None):
        """Send file response."""
        self.send_response(200)
        self.send_header('Content-Type', mime_type)
        self.send_header('Content-Length', len(content))
        if filename:
            self.send_header('Content-Disposition', f'inline; filename="{filename}"')
        # Allow cross-origin requests for images (Instagram fetches from their servers)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._handle_health()
        elif self.path == '/ready':
            self._handle_ready()
        elif self.path == '/live':
            self._handle_live()
        elif self.path == '/metrics':
            self._handle_metrics()
        elif self.path.startswith('/media/'):
            self._handle_media()
        else:
            self._send_json({'error': 'Not found'}, 404)

    def do_HEAD(self):
        """Handle HEAD requests (same as GET but no body)."""
        if self.path.startswith('/media/'):
            self._handle_media_head()
        else:
            # For other endpoints, just send headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

    def _handle_health(self):
        """Full health status with stats."""
        now = datetime.now(ZoneInfo(TIMEZONE))
        uptime = (now - self.start_time).total_seconds() if self.start_time else 0

        # Get stats if callback available
        stats = {}
        if self.stats_callback:
            try:
                stats = self.stats_callback()
            except Exception as e:
                stats = {'error': str(e)}

        # Get publisher status if callback available
        publishers = {}
        if self.publishers_callback:
            try:
                publishers = self.publishers_callback()
            except Exception as e:
                publishers = {'error': str(e)}

        response = {
            'status': 'healthy',
            'version': '2.0',
            'timestamp': now.isoformat(),
            'uptime_seconds': int(uptime),
            'uptime_human': self._format_uptime(uptime),
            'timezone': TIMEZONE,
            'stats': stats,
            'publishers': publishers
        }

        self._send_json(response)

    def _handle_ready(self):
        """Readiness probe - can this instance accept traffic?"""
        self._send_json({
            'status': 'ready',
            'timestamp': datetime.now(ZoneInfo(TIMEZONE)).isoformat()
        })

    def _handle_live(self):
        """Liveness probe - is the process alive?"""
        self._send_json({
            'status': 'alive',
            'timestamp': datetime.now(ZoneInfo(TIMEZONE)).isoformat()
        })

    def _handle_metrics(self):
        """Prometheus-compatible metrics (basic)."""
        stats = {}
        if self.stats_callback:
            try:
                stats = self.stats_callback()
            except Exception:
                pass

        uptime = (datetime.now(ZoneInfo(TIMEZONE)) - self.start_time).total_seconds() if self.start_time else 0

        # Prometheus format
        metrics = [
            f'# HELP postall_uptime_seconds Daemon uptime in seconds',
            f'# TYPE postall_uptime_seconds gauge',
            f'postall_uptime_seconds {int(uptime)}',
            f'',
            f'# HELP postall_checks_total Total checks performed',
            f'# TYPE postall_checks_total counter',
            f'postall_checks_total {stats.get("checks_performed", 0)}',
            f'',
            f'# HELP postall_posts_published_total Total posts published',
            f'# TYPE postall_posts_published_total counter',
            f'postall_posts_published_total {stats.get("posts_published", 0)}',
            f'',
            f'# HELP postall_posts_failed_total Total posts failed',
            f'# TYPE postall_posts_failed_total counter',
            f'postall_posts_failed_total {stats.get("posts_failed", 0)}',
        ]

        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write('\n'.join(metrics).encode())

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")

        return ' '.join(parts)

    def _handle_media(self):
        """
        Serve static files from output directory.

        URL format: /media/{relative_path_to_file}
        Example: /media/2026-01-13_week3/instagram-posts/images/post1.png

        This enables Instagram API to fetch images from this server.
        """
        if self.media_server is None:
            self._send_json({
                'error': 'Media server not configured',
                'hint': 'MediaServer instance not set on handler'
            }, 500)
            return

        # Extract relative path from URL (remove /media/ prefix)
        relative_path = unquote(self.path[7:])  # len('/media/') = 7

        if not relative_path:
            self._send_json({
                'error': 'No file path specified',
                'usage': '/media/{relative_path_to_file}'
            }, 400)
            return

        # Get file from media server
        file_data = self.media_server.get_file(relative_path)

        if file_data is None:
            self._send_json({
                'error': 'File not found or not allowed',
                'path': relative_path
            }, 404)
            return

        # Get filename for Content-Disposition header
        from pathlib import Path
        filename = Path(relative_path).name

        # Send the file
        self._send_file(
            content=file_data['content'],
            mime_type=file_data['mime_type'],
            filename=filename
        )

    def _handle_media_head(self):
        """
        Handle HEAD request for media files.
        Returns headers only (no body) - useful for checking if file exists.
        """
        if self.media_server is None:
            self.send_response(500)
            self.end_headers()
            return

        relative_path = unquote(self.path[7:])

        if not relative_path:
            self.send_response(400)
            self.end_headers()
            return

        file_data = self.media_server.get_file(relative_path)

        if file_data is None:
            self.send_response(404)
            self.end_headers()
            return

        # Send headers only (no body for HEAD)
        self.send_response(200)
        self.send_header('Content-Type', file_data['mime_type'])
        self.send_header('Content-Length', file_data['size'])
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()


class HealthServer:
    """
    HTTP server for health checks and media serving.

    Runs in a separate thread to not block the main daemon.

    Endpoints:
    - /health  - Full health status
    - /ready   - Readiness probe
    - /live    - Liveness probe
    - /metrics - Prometheus metrics
    - /media/* - Static file serving for images (Instagram support)
    """

    def __init__(
        self,
        port: int = 8080,
        stats_callback: Callable = None,
        publishers_callback: Callable = None,
        enable_media_server: bool = True
    ):
        """
        Initialize the health server.

        Args:
            port: Port to listen on
            stats_callback: Function that returns daemon stats dict
            publishers_callback: Function that returns publisher status dict
            enable_media_server: Enable /media/* endpoint for serving images
        """
        self.port = port
        self.start_time = datetime.now(ZoneInfo(TIMEZONE))
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[Thread] = None

        # Set class-level callbacks for handler
        HealthHandler.start_time = self.start_time
        HealthHandler.stats_callback = stats_callback
        HealthHandler.publishers_callback = publishers_callback

        # Initialize media server if enabled
        if enable_media_server:
            from postall.cloud.media_server import MediaServer
            HealthHandler.media_server = MediaServer()
        else:
            HealthHandler.media_server = None

    def start(self):
        """Start the health server in a background thread."""
        self._server = HTTPServer(('0.0.0.0', self.port), HealthHandler)

        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        return self

    def stop(self):
        """Stop the health server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Convenience function for simple usage
def run_health_server(port: int = 8080):
    """Run health server standalone (for testing)."""
    server = HealthServer(port=port)
    server.start()
    print(f"Health server running on http://0.0.0.0:{port}")
    print("Endpoints:")
    print("  /health  - Full health status")
    print("  /ready   - Readiness probe")
    print("  /live    - Liveness probe")
    print("  /metrics - Prometheus metrics")
    print("  /media/* - Static file serving (images for Instagram)")

    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        server.stop()


if __name__ == '__main__':
    run_health_server()
