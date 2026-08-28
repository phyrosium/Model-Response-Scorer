# Shared dependency layer for both stages.
FROM node:20-slim AS base
WORKDIR /app
COPY package.json ./
RUN npm install

# Local development: the Vite dev server, with the source bind-mounted over it
# by docker-compose. Selected via `target: dev`.
FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Deployment: build the static bundle, then serve it.
# This is the default (last) stage, which is what Railway builds.
FROM base AS prod
COPY . .
# VITE_API_URL is substituted into the JavaScript here, during the build.
# It is not read at run time, so changing it needs a rebuild, not a restart.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# `vite preview` is a development convenience and refuses any Host it does not
# recognise, which means a 403 on every request to a deployed domain. Serve the
# built output with a static server instead. -s rewrites unknown paths to
# index.html, which react-router needs for /how-to and friends.
RUN npm install -g serve@14.2.4
# ${PORT} expanded at run time by the platform.
CMD ["sh", "-c", "serve -s dist -l ${PORT:-4173}"]
