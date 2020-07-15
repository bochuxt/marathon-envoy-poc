import redis
r = redis.Redis(host='localhost', port=6379, db=0)
r.set('foo', 'bar')
#True
r.get('foo')
#b'bar'