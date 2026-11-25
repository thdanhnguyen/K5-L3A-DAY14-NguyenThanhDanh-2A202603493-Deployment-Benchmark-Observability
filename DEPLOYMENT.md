# Deployment Information — Day 14 Lab

## Public URL
https://k5-l3a-day14-nguyenthanhdanh-2a202603493.onrender.com

## Platform
Render (Docker multi-stage từ thư mục `06-lab-complete/` + Redis)

## Test Commands

Đặt `BASE` và `AGENT_API_KEY` (key đã cấu hình trên Render Environment Variables, không commit key thật vào repo):

```bash
BASE="https://k5-l3a-day14-nguyenthanhdanh-2a202603493.onrender.com"
```

### 1. Health Check (Liveness — mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
```
Kết quả thực tế: `200` (`{"status":"ok","uptime_seconds":63.5,...}`)

### 2. Readiness Check (Redis connected — mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
```
Kết quả thực tế: `200` (`{"ready":true,"redis":"connected"}`)

### 3. API Test không có key (Authentication — mong đợi `401`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
```
Kết quả thực tế: `401` (`{"detail":"Invalid or missing API key"}`)

### 4. API Test có API key (mong đợi `200`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

## Environment Variables Set (trên Render Dashboard)
- `ENVIRONMENT` (`production`)
- `AGENT_API_KEY` *(secret — đặt trực tiếp trên Render Environment, không ghi trong code)*
- `REDIS_URL` *(kết nối Redis trên cloud, không ghi trong code)*
- `RATE_LIMIT_PER_MINUTE` (`10`)
- `DAILY_BUDGET_USD` (`1.0`)
- `MONTHLY_BUDGET_USD` (`10.0`)
- `PORT` *(do Render tự inject)*

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
