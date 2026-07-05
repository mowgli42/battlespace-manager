FROM node:22-alpine AS build
WORKDIR /app
COPY services/battlespace-display/web/package.json services/battlespace-display/web/package-lock.json* ./
RUN npm install
COPY services/battlespace-display/web/ .
ARG VITE_API_URL=http://battlespace-display-api:8004
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine
RUN echo 'server { listen 8081; root /usr/share/nginx/html; location = /landing { proxy_pass http://battlespace-display-api:8004/landing; } location /api/portal/ { proxy_pass http://battlespace-display-api:8004/api/portal/; } location / { try_files $uri $uri/ /index.html; } location /api/ { proxy_pass http://battlespace-display-api:8004; } }' > /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8081
