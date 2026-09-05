package main

import (
	"net/http"
	"sync"
	"time"
)

// rateLimiter es un limitador por clave (IP) con ventana deslizante en memoria.
type rateLimiter struct {
	mu     sync.Mutex
	limit  int
	window time.Duration
	hits   map[string][]time.Time
}

func newRateLimiter(limit int, window time.Duration) *rateLimiter {
	return &rateLimiter{limit: limit, window: window, hits: make(map[string][]time.Time)}
}

func (rl *rateLimiter) allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-rl.window)

	if len(rl.hits) > 100_000 {
		// vaciado defensivo ante abuso de IPs distintas
		rl.hits = make(map[string][]time.Time)
	}

	recent := rl.hits[key][:0]
	for _, t := range rl.hits[key] {
		if t.After(cutoff) {
			recent = append(recent, t)
		}
	}
	if len(recent) >= rl.limit {
		rl.hits[key] = recent
		return false
	}
	rl.hits[key] = append(recent, now)
	return true
}

// clientIP extrae la IP del cliente (sin confiar en X-Forwarded-For: no hay proxy).
func clientIP(r *http.Request) string {
	host := r.RemoteAddr
	if i := len(host) - 1; i >= 0 {
		for j := 0; j < len(host); j++ {
			if host[j] == ':' {
				return host[:j]
			}
		}
	}
	return host
}

// limitMiddleware rechaza con 429 si la clave (IP) supera el límite.
func limitMiddleware(rl *rateLimiter, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if !rl.allow(clientIP(r)) {
			http.Error(w, "demasiadas peticiones, inténtalo más tarde", http.StatusTooManyRequests)
			return
		}
		next(w, r)
	}
}

// maxBytes limita el tamaño del cuerpo de la petición.
func maxBytes(n int64, next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, n)
		next(w, r)
	}
}