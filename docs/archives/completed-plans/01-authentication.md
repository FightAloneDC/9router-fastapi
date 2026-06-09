# Phase 1: Login Page & Authentication

## Status: COMPLETE

## Overview
Password-based authentication with JWT tokens. Follows the 9Router pattern:
single password login (no username), default password `123456`, auto-creates
admin user on first login.

## Backend Architecture

### Models
- `User` (users table): id (UUID), username, hashed_password, is_active, timestamps

### Endpoints
| Method | Path           | Auth | Description                    |
|--------|----------------|------|--------------------------------|
| GET    | /auth/status   | No   | Check if login required        |
| POST   | /auth/login    | No   | Login with password → JWT      |
| POST   | /auth/register | No   | Register new user              |
| GET    | /auth/me       | Yes  | Get current user info          |

### Auth Flow
1. Frontend calls GET /auth/status → { requireLogin, hasPassword }
2. User submits password → POST /auth/login → { access_token }
3. Token stored in localStorage, attached as Bearer header
4. 401 responses trigger automatic logout + redirect to /login

### Password Hashing
- Uses `bcrypt` directly (not passlib — incompatibility with bcrypt >= 4.1)
- Default password: `123456` (creates admin user on first login)

### JWT
- Algorithm: HS256
- Expiry: 24 hours
- Secret: from config (SECRET_KEY env var or default)
- Payload: { sub: username, exp: timestamp }

## Frontend Architecture

### Components
- `LoginPage.jsx`: Password form, default password hint, loading states
- `AuthLayout.jsx`: Full-screen gradient background wrapper
- `authStore.js` (Zustand): Token management, login/logout/checkAuth
- `auth.js` (API client): login, status, verify, register

### Protected Routes
- `ProtectedRoute` component checks `isAuthenticated` from authStore
- Redirects to `/login` if not authenticated
- All dashboard routes wrapped in `ProtectedRoute`

### API Client
- Axios instance with baseURL `/api`
- Request interceptor: attaches Bearer token
- Response interceptor: 401 → logout + redirect

## Environment Setup
- Docker PostgreSQL 16 (container: 9router-postgres)
- Vite proxy: `/api` → `localhost:8000` with path rewrite

## Verification
- [x] GET /auth/status returns { requireLogin, hasPassword }
- [x] POST /auth/login with "123456" creates admin + returns JWT
- [x] GET /auth/me with valid token returns user info
- [x] Wrong password returns 401
- [x] Frontend builds without errors
- [x] Vite proxy correctly rewrites /api prefix
