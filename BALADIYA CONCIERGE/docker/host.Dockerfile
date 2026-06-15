FROM nginx:alpine

COPY host/index.html /usr/share/nginx/html/index.html
COPY host/assets/ /usr/share/nginx/html/assets/
COPY host/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
