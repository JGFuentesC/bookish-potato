package main

import (
	"bytes"
	"context"
	"crypto/rand"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

//go:embed all:dist
var distFS embed.FS

type ctxKey string

const ctxKeyEmail ctxKey = "email"

type LoginCreds struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

type Claims struct {
	Email string `json:"email"`
	jwt.RegisteredClaims
}

// jwtSecret se inyecta vía entorno; si falta, se genera uno efímero (solo dev).
var jwtSecret = func() []byte {
	s := os.Getenv("JWT_SECRET")
	if s == "" {
		log.Println("aviso: JWT_SECRET no definida; usando secreto efímero (sesiones invalidadas al reiniciar)")
		b := make([]byte, 32)
		_, _ = rand.Read(b)
		return b
	}
	return []byte(s)
}()

func main() {
	// Soporte de healthcheck del contenedor: /server -healthcheck hace un
	// self-check HTTP sobre /healthz y sale (docker HEALTHCHECK).
	for _, arg := range os.Args[1:] {
		if arg == "-healthcheck" {
			if err := runHealthcheck(); err != nil {
				log.Fatalf("healthcheck: %v", err)
			}
			return
		}
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	sub, err := fs.Sub(distFS, "dist")
	if err != nil {
		log.Fatalf("spa embebida: %v", err)
	}

	mux := http.NewServeMux()

	// Limitadores por IP (memoria): login = anti fuerza bruta; API = anti abuso
	// (nl2sql dispara llamadas al LLM).
	loginLimiter := newRateLimiter(10, time.Minute)
	apiLimiter := newRateLimiter(30, time.Minute)

	// Public routes (SPA + login + health)
	mux.HandleFunc("GET /healthz", handleHealthz)
	mux.HandleFunc("POST /api/login", maxBytes(1<<20, limitMiddleware(loginLimiter, handleLogin)))
	mux.HandleFunc("GET /api/verify", handleVerify)
	mux.HandleFunc("GET /", makeSpaHandler(sub))

	// Protected API routes - require JWT
	mux.HandleFunc("POST /api/v1/query", maxBytes(1<<20, limitMiddleware(apiLimiter, authHandler(makeQueryHandler))))
	mux.HandleFunc("POST /api/v1/nl2sql", maxBytes(1<<20, limitMiddleware(apiLimiter, authHandler(makeNl2SqlProxyHandler))))
	mux.HandleFunc("GET /api/me", authHandler(makeMeHandler))

	addr := ":" + port
	log.Printf("genbi-futbol app escuchando en %s", addr)
	if err := http.ListenAndServe(addr, securityHeaders(mux)); err != nil {
		log.Fatal(err)
	}
}

// jwtParseOptions fija el algoritmo HS256 y el issuer para evitar
// confusión de algoritmos (alg confusion) y tokens de terceros.
func jwtParseOptions() []jwt.ParserOption {
	return []jwt.ParserOption{
		jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
		jwt.WithIssuer("genbi-futbol"),
	}
}

// authHandler wraps an http.HandlerFunc with JWT authentication.
func authHandler(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		authHeader := r.Header.Get("Authorization")
		if authHeader == "" || len(authHeader) < 7 || authHeader[:7] != "Bearer " {
			http.Error(w, "missing or invalid authorization header", http.StatusUnauthorized)
			return
		}

		tokenString := authHeader[7:]
		claims := &Claims{}
		token, err := jwt.ParseWithClaims(
			tokenString,
			claims,
			func(t *jwt.Token) (interface{}, error) { return jwtSecret, nil },
			jwtParseOptions()...,
		)
		if err != nil || !token.Valid {
			http.Error(w, "invalid or expired token", http.StatusUnauthorized)
			return
		}

		ctx := context.WithValue(r.Context(), ctxKeyEmail, claims.Email)
		next(w, r.WithContext(ctx))
	}
}

func securityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
		next.ServeHTTP(w, r)
	})
}

func handleHealthz(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	var creds LoginCreds
	if err := json.NewDecoder(r.Body).Decode(&creds); err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			http.Error(w, "cuerpo demasiado grande", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(w, "invalid request", http.StatusBadRequest)
		return
	}

	// Credenciales de demo configuradas por entorno (solo POC/curso).
	email := os.Getenv("AUTH_EMAIL")
	if email == "" {
		email = "user@genbi.com"
	}
	pass := os.Getenv("AUTH_PASSWORD")
	if pass == "" {
		pass = "password123"
	}

	if creds.Email != email || creds.Password != pass {
		http.Error(w, "invalid credentials", http.StatusUnauthorized)
		return
	}

	claims := Claims{
		Email: creds.Email,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(24 * time.Hour)),
			Issuer:    "genbi-futbol",
		},
	}

	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	tokenString, err := token.SignedString(jwtSecret)
	if err != nil {
		http.Error(w, "could not generate token", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "logged in",
		"token":  tokenString,
		"email":  creds.Email,
	})
}

func makeSpaHandler(dist fs.FS) http.HandlerFunc {
	fileServer := http.FileServer(http.FS(dist))
	return func(w http.ResponseWriter, r *http.Request) {
		path := strings.TrimPrefix(r.URL.Path, "/")
		if _, err := fs.Stat(dist, path); err == nil {
			fileServer.ServeHTTP(w, r)
			return
		}
		index, err := fs.ReadFile(dist, "index.html")
		if err != nil {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write(index)
	}
}

// makeQueryHandler reenvía una consulta autenticada al sidecar (capa semántica).
func makeQueryHandler(w http.ResponseWriter, r *http.Request) {
	makeSidecarProxy("/api/v1/query", w, r)
}

// makeNl2SqlProxyHandler reenvía una pregunta NL2SQL autenticada al sidecar.
func makeNl2SqlProxyHandler(w http.ResponseWriter, r *http.Request) {
	makeSidecarProxy("/api/v1/nl2sql", w, r)
}

// makeSidecarProxy reenvía POST al sidecar con timeout amplio (NL2SQL llama al LLM).
func makeSidecarProxy(path string, w http.ResponseWriter, r *http.Request) {
	sidecarURL := os.Getenv("SIDECAR_URL")
	if sidecarURL == "" {
		http.Error(w, "SIDECAR_URL no configurada", http.StatusServiceUnavailable)
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil {
		var mbe *http.MaxBytesError
		if errors.As(err, &mbe) {
			http.Error(w, "cuerpo demasiado grande", http.StatusRequestEntityTooLarge)
			return
		}
		http.Error(w, "no se pudo leer el cuerpo", http.StatusBadRequest)
		return
	}

	target := strings.TrimSuffix(sidecarURL, "/") + path
	req, err := http.NewRequest(http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		http.Error(w, "no se pudo crear la petición", http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 120 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		http.Error(w, "sidecar no disponible", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	_, _ = io.Copy(w, resp.Body)
}

func makeMeHandler(w http.ResponseWriter, r *http.Request) {
	// el middleware ya validó el JWT; recuperamos el email del contexto
	email, _ := r.Context().Value(ctxKeyEmail).(string)
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{"email": email})
}

func handleVerify(w http.ResponseWriter, r *http.Request) {
	// Check for JWT in Authorization header
	authHeader := r.Header.Get("Authorization")
	if authHeader == "" || len(authHeader) < 7 || authHeader[:7] != "Bearer " {
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "missing token"})
		return
	}

	tokenString := authHeader[7:]
	claims := &Claims{}
	token, err := jwt.ParseWithClaims(
		tokenString,
		claims,
		func(t *jwt.Token) (interface{}, error) { return jwtSecret, nil },
		jwtParseOptions()...,
	)
	if err != nil || !token.Valid {
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "invalid token"})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "verified", "email": claims.Email})
}

// runHealthcheck hace un GET a /healthz y devuelve error si no responde 200.
func runHealthcheck() error {
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%s/healthz", port))
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("status %d", resp.StatusCode)
	}
	return nil
}