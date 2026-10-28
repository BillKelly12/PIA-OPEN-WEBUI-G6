"""Shared helpers for the verification scenario (API level, synthetic data only)."""
import json
import requests

BASE = 'http://127.0.0.1:8080'


def jprint(label, obj):
    print(f'--- {label}')
    print(json.dumps(obj, indent=2, default=str)[:3000])


def signup_first_admin(name, email, password):
    r = requests.post(f'{BASE}/api/v1/auths/signup', json={'name': name, 'email': email, 'password': password, 'profile_image_url': ''})
    return r


def signin(email, password):
    s = requests.Session()
    r = s.post(f'{BASE}/api/v1/auths/signin', json={'email': email, 'password': password})
    return s, r


def bearer(token):
    return {'Authorization': f'Bearer {token}'}
