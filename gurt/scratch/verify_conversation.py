import sys
import io
import requests
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
base_url = 'http://127.0.0.1:8000'

print('=== TEST 1: I want to plan a new event ===')
r1 = requests.post(f'{base_url}/api/chat', json={'message': 'I want to plan a new event', 'event_id': 'evt-dubhacks-2026'})
d1 = r1.json()
print('STATUS 1:', r1.status_code)
print('TEXT 1:\n', d1.get('text'))
conv_id = d1.get('conversation_id')

print('\n=== TEST 2: Providing Loveable Community Workshop details ===')
msg2 = "It a Loveable Community Workshop. I'm expecting 30 people but we need ot get people to RSVP for it first. The budget right now is $400 but I'm open to looking for external sponsorships"
r2 = requests.post(f'{base_url}/api/chat', json={'message': msg2, 'conversation_id': conv_id, 'event_id': 'evt-dubhacks-2026'})
d2 = r2.json()
print('STATUS 2:', r2.status_code)
print('SWITCHED EVENT ID:', d2.get('switched_event_id'))
print('TOOLS 2:', [t.get('tool') for t in d2.get('tool_calls', [])])
print('TEXT 2:\n', d2.get('text'))

new_event_id = d2.get('switched_event_id') or 'evt-dubhacks-2026'

print('\n=== TEST 3: Are these sponsors confirmed? ===')
r3 = requests.post(f'{base_url}/api/chat', json={'message': 'Are these sponsors confirmed?', 'conversation_id': conv_id, 'event_id': new_event_id})
d3 = r3.json()
print('STATUS 3:', r3.status_code)
print('TEXT 3:\n', d3.get('text'))

print('\n=== TEST 4: What are u saying? ===')
r4 = requests.post(f'{base_url}/api/chat', json={'message': 'what are u saying?', 'conversation_id': conv_id, 'event_id': new_event_id})
d4 = r4.json()
print('STATUS 4:', r4.status_code)
print('TEXT 4:\n', d4.get('text'))
