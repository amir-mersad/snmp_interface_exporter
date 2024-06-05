from easysnmp import Session
from prometheus_client import start_http_server, Gauge
import yaml
import time
import threading

def load_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

def get_snmp_data(ip, community, oid):
    session = Session(hostname=ip, community=community, version=2)
    try:
        response = session.get(oid)
        return int(response.value)
    except Exception as e:
        print(f"SNMP error: {e}")
        return None

def poll_router(router, gauges):
    ip = router['ip']
    community = router.get('community', 'public')
    interval = router.get('interval', 60)
    oids = router['oids']

    lower_counters = {}
    while True:
        start_time = time.time()

        for oid_name, oid_value in oids.items():
            metric_name = f"{router['name']}_router_{ip.replace('.', '_')}_{oid_name}"

            if metric_name not in lower_counters:
                lower_counters[metric_name] = get_snmp_data(ip, community, oid_value)
                if lower_counters[metric_name] is None:
                    gauges[metric_name].set(0)

        time.sleep(interval)

        elapsed_time = time.time() - start_time

        for oid_name, oid_value in oids.items():
            metric_name = f"{router['name']}_router_{ip.replace('.', '_')}_{oid_name}"
            higher_counter = get_snmp_data(ip, community, oid_value)
            if higher_counter is None or lower_counters[metric_name] is None:
                gauges[metric_name].set(0)
                continue

            subtracted_counter = higher_counter - lower_counters[metric_name]
            bps = subtracted_counter / elapsed_time
            gauges[metric_name].set(bps)
            lower_counters[metric_name] = higher_counter

def main():
    config = load_config('config.yaml')
    gauges = {}

    for router_section in config.values():
        for router in router_section:
            ip = router['ip']
            oids = router['oids']

            for oid_name, oid_value in oids.items():
                metric_name = f"{router['name']}_router_{ip.replace('.', '_')}_{oid_name}"
                gauges[metric_name] = Gauge(metric_name, f"SNMP metric for {oid_name} on {ip}")

    start_http_server(9080)

    threads = []
    for router_section in config.values():
        for router in router_section:
            t = threading.Thread(target=poll_router, args=(router, gauges))
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    main()
