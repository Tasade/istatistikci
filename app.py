from http.server import ThreadingHTTPServer
import os

from statistical_agents.api import ApplicationHandler


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), ApplicationHandler)
    print(f"İstatistikçi agent sistemi: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
