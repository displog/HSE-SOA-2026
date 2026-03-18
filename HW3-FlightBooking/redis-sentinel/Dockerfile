FROM redis:7-alpine
RUN apk add --no-cache bind-tools
COPY redis-sentinel/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
