# Laboratorium 6: dopisz do ingestor/ingestor.py (paho-mqtt 2.x), PRZED client.connect(...):
import os

client.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASSWORD"])

# W .env (obok POSTGRES_... z Laboratorium 3):
#   MQTT_USER=ingestor
#   MQTT_PASSWORD=<to samo hasło co w broker/uzytkownicy>
# Ingestor łączy się dalej z broker:1883 -- wewnątrz sieci Dockera, port niewystawiony na zewnątrz.
