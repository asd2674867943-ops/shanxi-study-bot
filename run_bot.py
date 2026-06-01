"""Launcher for headless bot execution with health-check HTTP 
  server"""
  import sys
  import os
  import threading
  import http.server

  # Ensure the project root is on path
  sys.path.insert(0, os.path.dirname(__file__))

  # ── Tiny health-check server for Render Web Service ──
  PORT = int(os.environ.get("PORT", 10000))


  class HealthHandler(http.server.BaseHTTPRequestHandler):
      def do_GET(self):
          self.send_response(200)
          self.send_header("Content-type", "text/plain")
          self.end_headers()
          self.wfile.write(b"OK")

      def log_message(self, format, *args):
          pass  # silence access logs


  def start_health_server():
      server = http.server.HTTPServer(("0.0.0.0", PORT),
  HealthHandler)
      print(f"[health] listening on port {PORT}")
      server.serve_forever()


  if __name__ == "__main__":
      # Start health-check server in background
      t = threading.Thread(target=start_health_server, daemon=True)   
      t.start()

      # Start the Telegram bot (blocks forever)
      from study_bot.main import main
      main()
