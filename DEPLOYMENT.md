# Deployment Information — Day 14 Lab

## Public URL
https://nguyenthanhdanh-k5-lab014-l3a-production.up.railway.app

## Platform
Railway (Docker multi-stage từ thư mục `06-lab-complete/` + Railway Redis)

## Test Commands

Đặt `BASE` và `AGENT_API_KEY` (key đã cấu hình trên Railway Variables, không commit key thật vào repo):

```bash
BASE="https://nguyenthanhdanh-k5-lab014-l3a-production.up.railway.app"
```

### 1. Health Check (Liveness — mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
```

### 2. Readiness Check (Redis connected — mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
```

### 3. API Test không có key (Authentication — mong đợi `401`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
```

### 4. API Test có API key (mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Environment Variables Set (trên Railway Dashboard)
- `ENVIRONMENT` (`production`)
- `AGENT_API_KEY` *(secret — đặt trực tiếp trên Railway Variables, không ghi trong code)*
- `REDIS_URL` *(reference tới service Redis trên Railway: `${{Redis.REDIS_URL}}`)*
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)
- `MONTHLY_BUDGET_USD` (`10.0`)
- `PORT` *(do Railway tự inject)*

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
