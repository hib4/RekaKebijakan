FROM node:22-alpine AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS build

ARG VITE_API_URL=/backend
ARG VITE_DEMO_MODE=false
ENV VITE_API_URL=${VITE_API_URL} \
    VITE_DEMO_MODE=${VITE_DEMO_MODE}

COPY . .
RUN npm run build

FROM deps AS test

COPY . .
CMD ["sh", "-c", "npm test && npm run lint && npm run build"]

FROM nginx:1.29-alpine AS production

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
