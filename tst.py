from kafka import KafkaProducer, KafkaConsumer
import json, time

# Producer test
p = KafkaProducer(bootstrap_servers='localhost:9092', value_serializer=lambda v: json.dumps(v).encode())
p.send('ccu-incidents', {'test': 'hello'})
p.flush()
print('sent')

# Consumer test (stop with Ctrl+C)
c = KafkaConsumer('ccu-incidents', bootstrap='localhost:9092', auto_offset_reset='earliest', value_deserializer=lambda m: json.loads(m.decode()))
for msg in c:
    print(msg.value)
