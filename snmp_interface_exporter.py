from easysnmp import Session
from prometheus_client import start_http_server, Gauge
import yaml
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Global configuration dictionary and a dictionary to keep track of active gauges and threads
config = {}
gauges = {}
threads = {}
threads_lock = threading.Lock()

def load_config(file_path):
    global config
    with open(file_path, 'r') as file:
        config = yaml.safe_load(file)
    update_gauges()

class ConfigChangeHandler(FileSystemEventHandler):
    def __init__(self, config_path):
        self.config_path = config_path

    def on_modified(self, event):
        if event.src_path == self.config_path:
            print("Configuration file changed. Reloading...")
            load_config(self.config_path)

def get_snmp_data(ip, community, oid):
    session = Session(hostname=ip, community=community, version=2)
    try:
        response = session.get(oid)
        return int(response.value)
    except Exception as e:
        print(f"SNMP error for {ip}: {e}")
        return None

def poll_router(router, stop_event):
    global gauges
    ip = router['ip']
    community = router.get('community', 'public')
    interval = router.get('interval', 60)
    oids = router['oids']

    lower_counters = {}
    while not stop_event.is_set():
        start_time = time.time()

        for oid_name, oid_value in oids.items():
            metric_name = f"{router['name']}_router_{ip.replace('.', '_')}_{oid_name}"

            if metric_name not in lower_counters:
                lower_counters[metric_name] = get_snmp_data(ip, community, oid_value)
                if lower_counters[metric_name] is None:
                    gauges[metric_name].set(-1)

        time.sleep(interval)

        elapsed_time = time.time() - start_time

        for oid_name, oid_value in oids.items():
            metric_name = f"{router['name']}_router_{ip.replace('.', '_')}_{oid_name}"
            higher_counter = get_snmp_data(ip, community, oid_value)
            if higher_counter is None or lower_counters[metric_name] is None:
                gauges[metric_name].set(-1)
                continue

            subtracted_counter = higher_counter - lower_counters[metric_name]
            bps = subtracted_counter / elapsed_time
            gauges[metric_name].set(bps)
            lower_counters[metric_name] = higher_counter

def update_gauges():
    global config, gauges, threads, threads_lock

    with threads_lock:
        # Stop and remove any threads for routers no longer in config
        active_router_keys = [f"{router['name']}_{router['ip']}" for router_section in config.values() for router in router_section]
        for router_key in list(threads.keys()):
            if router_key not in active_router_keys:
                print(f"Removing gauges and stopping thread for router: {router_key}")
                stop_event = threads[router_key]['stop_event']
                stop_event.set()
                threads[router_key]['thread'].join()
                del threads[router_key]

        # Add new routers from config
        for router_section in config.values():
            for router in router_section:
                router_key = f"{router['name']}_{router['ip']}"
                if router_key not in threads:
                    print(f"Adding new gauges and starting thread for router: {router_key}")
                    for oid_name in router['oids'].keys():
                        metric_name = f"{router['name']}_router_{router['ip'].replace('.', '_')}_{oid_name}"
                        if metric_name not in gauges:
                            gauges[metric_name] = Gauge(metric_name, f"SNMP metric for {oid_name} on {router['ip']}")

                    stop_event = threading.Event()
                    t = threading.Thread(target=poll_router, args=(router, stop_event))
                    t.start()
                    threads[router_key] = {'thread': t, 'stop_event': stop_event}

def main():
    config_path = "/usr/local/bin/snmp/config.yaml"
    load_config(config_path)

    # Start Prometheus HTTP server
    start_http_server(9080)

    # Set up the watchdog observer to watch the configuration file
    event_handler = ConfigChangeHandler(config_path)
    observer = Observer()
    observer.schedule(event_handler, path=config_path, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()

if __name__ == "__main__":
    main()
