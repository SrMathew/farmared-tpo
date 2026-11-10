"""Verifica que MongoDB (replica set) y Redis estén accesibles desde el contenedor."""
import os

from pymongo import MongoClient
import redis

mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

m = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
print("MongoDB ping:", m.admin.command("ping"))
print("Replica set:", m.admin.command("hello").get("setName"))
print("Redis ping:", redis.Redis.from_url(redis_url).ping())
