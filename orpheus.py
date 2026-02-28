import json
import logging
import os
import requests
import shutil
import time

from prometheus_client import Gauge, start_http_server
from qbittorrentapi import Client

def load_clients():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.json')
    try:
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        clients_config = config_data.get('clients', {})
        return {name: Client(host=url) for name, url in clients_config.items()}
    except Exception as e:
        logging.error(f"Error loading config.json: {e}")
        return {}


CLIENTS = load_clients()

TOTAL_UPLOAD = Gauge(
    'torrent_total_upload_bytes', 
    'Total uploaded bytes for a torrent', 
    ['torrent_name', 'hash']
)

METRICS_URL = "http://localhost:9091"

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def query_prometheus(query):
    try:
        response = requests.get(f"{METRICS_URL}/api/v1/query", params={"query": query})
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return data["data"]["result"]
        logging.error(f"Prometheus query error: {data.get('error')}")
    except Exception as e:
        logging.error(f"Error querying Prometheus: {e}")
    return []


def calculate_score(downloaded, uploaded, seeding_time, last_activity):
    current_ts = time.time()
    
    seeding_time_score = (max(seeding_time / 86400, 0.01)) ** 0.75

    time_since_activity = (current_ts - last_activity) / 86400
    last_activity_score = (max(time_since_activity, 0)) ** 1.5
        
    ratio_score = (uploaded / max(downloaded, 1)) * 100
    return (ratio_score / seeding_time_score) - last_activity_score


def process_torrents(torrents, deltas):
    for torrent in torrents:
        name = torrent["name"]
        info_hash = torrent["hash"]
        downloaded = torrent["downloaded"]
        uploaded = torrent["uploaded"]
        seeding_time = torrent["seeding_time"]
        total_size = torrent["total_size"]
        last_activity = torrent["last_activity"]
        added_on = torrent["added_on"]
        
        effective_downloaded = max(downloaded, total_size)
        effective_upload = deltas.get(info_hash, uploaded)

        torrent["score"] = calculate_score(effective_downloaded, effective_upload, seeding_time, last_activity)

        TOTAL_UPLOAD.labels(torrent_name=name, hash=info_hash).set(uploaded)


def manage_disk_space(torrents):
    total, used, free = shutil.disk_usage("/lts")

    limit = total * 0.2
    if free >= limit:
        logging.info(f"Disk limit -- {bcolors.OKGREEN}{used / (total - limit) * 100:>6.2f}%{bcolors.ENDC} -- {bcolors.OKCYAN}({(free - limit) / (1024**3):.0f} GB remaining){bcolors.ENDC}")
        return

    required = limit - free
    logging.info(f"Disk limit -- {bcolors.WARNING}{used / (total - limit) * 100:>6.2f}%{bcolors.ENDC} -- {bcolors.WARNING}({(required / (1024**3)):.0f} GB required){bcolors.ENDC}")

    aleady_tagged = 0
    tagged = 0
    reclaimed = 0

    for torrent in torrents:
        if required <= 0:
            break

        if "met" not in torrent["tags"]:
            continue

        if "remove" in torrent["tags"]:
            required -= torrent["total_size"]
            reclaimed += torrent["total_size"]
            aleady_tagged += 1
            logging.info(f"Already tagged")
            logging.info(f"    {torrent['client']} - {torrent['category']} - {torrent['tags']}")
            logging.info(f"    {torrent['name']}")
            logging.info(f"    {bcolors.OKCYAN}({torrent['score']:.0f} points, {torrent['total_size'] / (1024**3):.0f} GB){bcolors.ENDC}")
            continue

        qbt = CLIENTS[torrent["client"]]
        qbt.torrents_add_tags(tags="remove", torrent_hashes=torrent["hash"])
        required -= torrent["total_size"]
        reclaimed += torrent["total_size"]
        tagged += 1
        logging.info(f"Tagged")
        logging.info(f"    {torrent['client']} - {torrent['category']} - {torrent['tags']}")
        logging.info(f"    {torrent['name']}")
        logging.info(f"    {bcolors.OKCYAN}({torrent['score']:.0f} points, {torrent['total_size'] / (1024**3):.0f} GB){bcolors.ENDC}")

    logging.info(f"Found {aleady_tagged} already tagged torrents and tagged {tagged} new torrents to be removed. {reclaimed / (1024**3):.0f} GB to be reclaimed.")


def fetch_metrics():
    torrents = []
    met_torrents_count = 0
    met_torrents_size = 0
    for name, qbt in CLIENTS.items():
        for torrent in qbt.torrents_info(SIMPLE_RESPONSES=True):
            torrent["client"] = name
            torrents.append(torrent)

            if "met" in torrent["tags"]:
                met_torrents_count += 1
                met_torrents_size += torrent["total_size"]

    logging.info(f"Fetched {len(torrents):>6} torrents  {bcolors.OKCYAN}({met_torrents_count} met, {met_torrents_size / (1024**3):.0f} GB reclaimable){bcolors.ENDC}")
    
    full_history_hashes = set()
    results_history = query_prometheus('torrent_total_upload_bytes offset 30d')
    for item in results_history:
        full_history_hashes.add(item['metric']['hash'])

    deltas = {}
    if full_history_hashes:
        hash_regex = "|".join(full_history_hashes)
        results = query_prometheus(f'increase(torrent_total_upload_bytes{{hash=~"{hash_regex}"}}[30d])')
        for item in results:
            info_hash = item['metric'].get('hash')
            value = float(item['value'][1])
            deltas[info_hash] = value

    d30 = len(results_history)
    d28 = len(query_prometheus('torrent_total_upload_bytes offset 28d')) - d30
    d21 = len(query_prometheus('torrent_total_upload_bytes offset 21d')) - d30 - d28
    d14 = len(query_prometheus('torrent_total_upload_bytes offset 14d')) - d30 - d28 - d21
    d7 = len(query_prometheus('torrent_total_upload_bytes offset 7d')) - d30 - d28 - d21 - d14
    d0 = len(query_prometheus('torrent_total_upload_bytes')) - d30 - d28 - d21 - d14 - d7

    logging.info(f"Fetched {len(deltas):>6} deltas    {bcolors.OKCYAN}({d28} >28d, {d21} >21d, {d14} >14d, {d7} >7d, {d0} <7d){bcolors.ENDC}")
    
    process_torrents(torrents, deltas)

    torrents.sort(key=lambda x: x['score'])

    manage_disk_space(torrents)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    start_http_server(8001, addr='127.0.0.1')
    interval_seconds = 300
    
    while True:
        t0 = int(time.time())

        fetch_metrics()

        t1 = int(time.time())
        time.sleep(max(0, interval_seconds - (t1 - t0) - t0 % interval_seconds))

if __name__ == "__main__":
    main()