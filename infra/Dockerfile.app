FROM node:22-alpine AS web
WORKDIR /build
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM golang:1.26.5-alpine AS builder
WORKDIR /src
COPY backend/go.mod ./
RUN go mod download
COPY backend/ ./
COPY --from=web /build/dist ./cmd/server/dist
WORKDIR /src/cmd/server
RUN CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/server .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/server /server
USER nonroot
EXPOSE 8080
HEALTHCHECK CMD ["/server", "-healthcheck"]
ENTRYPOINT ["/server"]