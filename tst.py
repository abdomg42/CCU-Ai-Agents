from kafka import KafkaProducer
import json
p = KafkaProducer(bootstrap_servers='127.0.0.1:9092', value_serializer=lambda v: json.dumps(v).encode())
p.send('ccu-incidents', value={"source":"zammad","payload":{"title":"Test fibre","description":"Client acc-12345, service svc-fiber-12345, commande ord-2026-001. Coupure Internet fibre."}})
p.flush()
print("sent")
# import psycopg2
# c=psycopg2.connect(host='localhost', port=5432, user='inetum', password='inetum', dbname='inetum')
# c.cursor().execute('SELECT 1')
# print('ok')