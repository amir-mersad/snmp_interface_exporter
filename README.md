# snmp_interface_exporter
prometheus's snmp_exporter but for monitoring interface traffic with per ip oid.
This python code gives you the traffic as byte and you cant turn it into bit in grafana. (multiply by 8)
If you change the content of config.yaml file you need to restart the python app.
On case there is a problem with the remote host, snmp_exporter will return the value of "-1".
We can use an alert (threshold of below 0) to detect problems.
