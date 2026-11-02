FROM node:20-alpine AS build
WORKDIR /web
COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY . .
ARG REACT_APP_BACKEND_URL=
ARG REACT_APP_GOOGLE_CLIENT_ID=
RUN CI=false yarn build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /web/build /usr/share/nginx/html
EXPOSE 80
