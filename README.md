# snmp_interface_exporter
prometheus's snmp_exporter but for monitoring interface traffic with per ip oid.
the python code gives you the traffic as byte and you cant turn it into bit in grafana. (multiply by 8)
if you change the content of config.yaml file you need to restart the python app.
