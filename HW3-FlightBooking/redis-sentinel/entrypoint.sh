#!/bin/sh
set -e
echo "Waiting for redis_master DNS..."
until dig +short redis_master | grep -q .; do
  sleep 2
done
REDIS_IP=$(dig +short redis_master | head -1)
echo "Resolved redis_master to $REDIS_IP"
echo "sentinel monitor mymaster $REDIS_IP 6379 1" > /tmp/sentinel.conf
echo "sentinel down-after-milliseconds mymaster 5000" >> /tmp/sentinel.conf
echo "sentinel failover-timeout mymaster 60000" >> /tmp/sentinel.conf
exec redis-server /tmp/sentinel.conf --sentinel
