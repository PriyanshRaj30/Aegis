# Aegis

**Abuse-Aware API Gateway**  
*Production-inspired protection for your APIs*

Aegis is a robust API Gateway designed to protect backend services from abuse, scraping, credential stuffing, and DDoS-like attacks.

It sits in front of your APIs and intelligently decides whether to allow, throttle, challenge, or block incoming requests in real-time.

### Key Features

- **JWT Authentication** + Role-Based Access Control (RBAC)
- **API Key Management** with per-key rate limits
- **Advanced Rate Limiting** (Token Bucket + Sliding Window)
- **Real-time Risk Engine** with scoring and automated actions (throttle/ban)
- **Multi-layer Caching** (Local + Redis)
- **Comprehensive Audit Logging** and Analytics
- **Background Jobs** for cleanup and maintenance
- **Docker-ready** setup

### Architecture

```
Client → Aegis Gateway → Backend Services
```

Built with Redis for distributed state, PostgreSQL for persistence, and layered caching for performance.

### Tech Stack

- **Backend**: Spring Boot 3
- **Security**: Spring Security + JWT
- **Database**: PostgreSQL
- **Cache & Rate Limiting**: Redis
- **ORM**: Hibernate / JPA
- **Container**: Docker + Docker Compose
- **Testing**: JUnit 5 + Testcontainers

*(Alternative: Can be implemented with FastAPI + Python if faster development is preferred)*

### Core Modules

- Authentication & Authorization
- API Key System
- Rate Limiting & Throttling
- Risk Scoring Engine
- Request Auditing & Analytics
- Background Task Management

### Getting Started

```bash
docker-compose up -d
```

Then run the application and explore:

- `POST /auth/login`
- `POST /api-keys`
- Protected endpoints under rate limiting & risk protection

### Project Goals

This project demonstrates real-world backend engineering challenges:
- Building resilient rate limiting at scale
- Implementing behavioral abuse detection
- Designing secure, observable systems
