#!/bin/sh

# nginx config variable injection
# envsubst < nginx-basic-auth.conf > /etc/nginx/conf.d/default.conf
cp nginx-basic-auth.conf /etc/nginx/conf.d/default.conf
sed -i s/{HOST1}/$HOST1/ /etc/nginx/conf.d/default.conf
sed -i s/{HOST2}/$HOST2/ /etc/nginx/conf.d/default.conf
sed -i s/{HOST3}/$HOST3/ /etc/nginx/conf.d/default.conf

# htpasswd for basic authentication
htpasswd -c -b /etc/nginx/.htpasswd $USER1 $PW1
htpasswd -b /etc/nginx/.htpasswd $USER2 $PW2
htpasswd -b /etc/nginx/.htpasswd $USER3 $PW3

nginx -g "daemon off;"