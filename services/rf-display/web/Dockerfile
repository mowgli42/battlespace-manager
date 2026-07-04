FROM node:22-alpine AS build
WORKDIR /app
COPY services/rf-display/web/package.json services/rf-display/web/package-lock.json* ./
RUN npm install
COPY services/rf-display/web/ .
ARG VITE_API_URL=http://rf-display-api:8005
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM nginx:alpine
RUN echo 'server { listen 8082; root /usr/share/nginx/html; location / { try_files $uri $uri/ /index.html; } location /api/ { proxy_pass http://rf-display-api:8005; } }' > /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8082
