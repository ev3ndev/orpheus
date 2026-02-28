# Orpheus

Orpheus is an application that ideally partners with qui to track the amount of uploaded data for each torrent over the last 30 days. When disk space is running low, it smartly selects the worst-performing torrents and tags them for removal.

## Prerequisites

- **`met` Tag**: Orpheus only evaluates torrents that currently have the `met` tag applied to them. You should use a qui automation or another third-party tool to apply this tag to torrents that have met their requirements and can be removed.
- **Removal Tool**: Orpheus does not delete torrents directly; it simply applies a `remove` tag. You must use a qui automation or another third-party tool to monitor for this tag and actually delete the torrents.

## Features

- **Performance Tracking**: Monitors the amount of uploaded data of individual torrents over a 30-day period.
- **Smart Cleanup Tagging**: Automatically identifies the worst-performing torrents and tags them with a `remove` label when disk space is running low.
- **Multi-Client Support**: Seamlessly tracks multiple qBittorrent instances. **Note**: Orpheus assumes all configured instances are using the same physical disk. You will need to run a separate instance of Orpheus for each individual disk you want to manage.

## Configuration

Orpheus uses a JSON configuration file to connect to your qBittorrent clients. 

To configure the application, create a file named `config.json` in the `config/` directory. You can use `config/config.example.json` as a starting point.

### Example `config/config.json`

```json
{
    "clients": {
        "client1": "http://localhost:7476/proxy/YOUR_API_KEY_HERE",
        "client2": "http://localhost:7476/proxy/00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    }
}
```

### Configuration Details

- **`clients`**: A dictionary where the key is a custom name for your torrent client (e.g., `"client1"`, `"client2"`) and the value is the HTTP URL to access that client's API.
- **Authentication**: Orpheus does not currently support authentication using a username and password natively. 
  - If your client requires authentication, you should use an API proxy (e.g. using qui, `http://localhost:7476/proxy/...`) or ensure the client is accessible without authentication (e.g. bypassing authentication from local network inside the qBittorrent WebUI settings).
  - You can also use a direct qBittorrent URL if authentication is disabled.

## Getting Started

Orpheus is designed to be run as a Docker container.

1. Ensure your `config/config.json` file is set up properly.
2. Build and run the Docker image (or use a `docker-compose.yml` to mount the `config/` directory into the container).
3. The application will start monitoring the configured clients, evaluate torrents with the `met` tag, and apply the `remove` tag when space is needed.
