# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns phát hiện trong `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong mã nguồn (dòng 17–18):** `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` ghi trực tiếp trong code. Nếu push lên GitHub (nhất là repo public), secret bị lộ ngay lập tức và nằm vĩnh viễn trong lịch sử git.
2. **Hardcode cấu hình ứng dụng (dòng 21–22):** `DEBUG = True`, `MAX_TOKENS = 500` không đọc từ biến môi trường, không thể đổi cấu hình linh hoạt giữa `dev` / `staging` / `production` mà không sửa code.
3. **Dùng `print()` thay cho structured logging và làm lộ secret ra log (dòng 33–34, 38):** `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` in thẳng API key ra stdout; hơn nữa `print()` không có timestamp, log level hay định dạng JSON để các hệ thống log aggregator (Loki, Datadog, Cloud Logging) phân tích.
4. **Không có health check / readiness endpoint (dòng 42–43):** Không có `/health` và `/ready`, nên cloud platform hoặc load balancer không thể biết container còn sống hay đã sẵn sàng nhận traffic để tự restart hoặc điều phối request.
5. **Bind cứng `host="localhost"` (dòng 51):** Chỉ lắng nghe trên loopback `127.0.0.1`, khi chạy trong Docker container hoặc trên cloud sẽ không nhận được kết nối từ bên ngoài (cần `0.0.0.0`).
6. **Cố định `port=8000` (dòng 52):** Không đọc biến môi trường `PORT` do các nền tảng như Railway, Render, Cloud Run tự inject.
7. **Bật `reload=True` (dòng 53):** Chế độ auto-reload chỉ dành cho development; dùng trong production gây tốn CPU/RAM theo dõi file và có thể làm sập/restart server bất ngờ.
8. **Không xử lý graceful shutdown (lifespan / `SIGTERM`):** Khi nền tảng gửi `SIGTERM` để tắt hoặc deploy phiên bản mới, server tắt đột ngột làm cắt ngang các request đang xử lý (in-flight requests).

### Exercise 1.2: Kết quả chạy bản `develop`

Chạy app trong `01-localhost-vs-production/develop/` và gọi `POST /ask?question=Hello`:

```bash
curl -X POST "http://localhost:8000/ask?question=Hello"
```

Kết quả trả về (`200 OK`):

```json
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log thực tế từ server cho thấy secret bị lộ trực tiếp ra stdout:

```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
```

### Exercise 1.3: Chạy bản `production` và bảng so sánh

Kết quả gọi các endpoint của `01-localhost-vs-production/production/app.py`:

- `GET http://localhost:8000/health` (`200 OK`):
  ```json
  {"status":"ok","uptime_seconds":1.7,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T07:35:09.112371+00:00"}
  ```
- `GET http://localhost:8000/ready` (`200 OK`):
  ```json
  {"ready":true}
  ```
- `POST http://localhost:8000/ask` với body `{"question": "Hello"}` (`200 OK`):
  ```json
  {"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","model":"gpt-4o-mini"}
  ```

#### Bảng so sánh `develop` vs `production`

| Feature | Develop (`develop/app.py`) | Production (`production/app.py` + `config.py`) | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG`, `MAX_TOKENS` trực tiếp trong code (dòng 17–22) | Tách vào `config.py` đọc từ env vars (`os.getenv`), có `validate()` fail-fast khi thiếu `AGENT_API_KEY` ở production (dòng 15–50) | Tránh lộ secret trên Git; tách biệt cấu hình khỏi code theo nguyên tắc 12-Factor để deploy chung một artifact qua dev/staging/prod. |
| **Host & Port** | Cố định `host="localhost"`, `port=8000`, `reload=True` (dòng 49–54) | Đọc `HOST` (mặc định `0.0.0.0`), `PORT` (mặc định `8000`), `reload=settings.debug` (dòng 194–199) | Container/cloud yêu cầu bind `0.0.0.0` để nhận traffic từ bên ngoài và lắng nghe đúng `PORT` do nền tảng cấp; tắt `reload` giúp ổn định hiệu năng. |
| **Health check** | Không có `/health` hay `/ready` | Có `GET /health` (liveness), `GET /ready` (readiness trả 503 nếu chưa sẵn sàng) và `GET /metrics` (dòng 135–173) | Cloud/orchestrator dựa vào `/health` để tự restart container lỗi và `/ready` để chỉ route traffic tới instance đã sẵn sàng. |
| **Logging** | Dùng `print()` thô và in cả `OPENAI_API_KEY` (dòng 33–38) | Dùng `logging` định dạng JSON có `time`, `level`, `msg`; chỉ log metadata (`question_length`, `client_ip`), không log secret (dòng 28–32, 111–122) | Đảm bảo bảo mật (không lộ secret), dễ truy vấn/cảnh báo tự động bằng các hệ thống tập trung log (Loki, ELK, Datadog). |
| **Shutdown** | Tắt đột ngột, không có lifecycle hook | Dùng FastAPI `lifespan` (hạ cờ `is_ready = False`, chờ request hoàn thành) + đăng ký `signal.SIGTERM` (dòng 39–67, 180–189) | Tránh lỗi 502/cắt ngang request người dùng khi scale down hoặc rolling deploy. |
| **CORS & Input validation** | Không cấu hình CORS; nhận `question` qua query string | Cấu hình `CORSMiddleware` theo `ALLOWED_ORIGINS`; nhận JSON body và trả `422` rõ ràng nếu thiếu `question` (dòng 77–82, 102–108) | Kiểm soát truy cập cross-origin an toàn hơn và chuẩn hoá API RESTful. |

---

## Part 2: Docker Containerization

### Exercise 2.1: Câu hỏi về `02-docker/develop/Dockerfile`

1. **Base image là gì?**
   - `python:3.11` (bản Python đầy đủ trên Debian, bao gồm nhiều công cụ build/hệ thống nên dung lượng lớn ~1 GB).
2. **Working directory là gì?**
   - `/app` (khai báo bằng `WORKDIR /app`). Mọi lệnh `COPY`, `RUN`, `CMD` sau đó đều thực thi tương đối từ `/app`.
3. **Tại sao `COPY requirements.txt` phải đứng trước `COPY app.py` (hay `COPY . .`)?**
   - Để tận dụng **Docker layer cache**. Mã nguồn thay đổi rất thường xuyên, còn `requirements.txt` ít thay đổi hơn. Khi đặt `COPY requirements.txt` + `RUN pip install` lên trước, các lần build sau chỉ sửa code sẽ tái sử dụng cache layer dependencies thay vì tải và cài lại toàn bộ thư viện.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?**
   - `CMD` định nghĩa lệnh mặc định khi chạy container và **dễ bị ghi đè** khi truyền tham số ở cuối `docker run <image> <command>`.
   - `ENTRYPOINT` định nghĩa tiến trình thực thi chính cố định của container; tham số truyền sau `docker run` sẽ được **nối thêm làm đối số** cho `ENTRYPOINT` (chỉ bị ghi đè khi dùng cờ `--entrypoint`). Khi dùng chung, `ENTRYPOINT` là lệnh chính còn `CMD` cung cấp đối số mặc định.

### Exercise 2.2: Build và chạy container `my-agent:develop`

Build từ thư mục gốc repo:

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --rm --name cp2-dev-test -p 8000:8000 my-agent:develop
curl -X POST "http://localhost:8000/ask?question=What+is+Docker%3F"
```

Kết quả trả về (`200 OK`):

```json
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build và so sánh kích thước image

Phân tích `02-docker/production/Dockerfile`:
- **Stage 1 (`builder`, từ `python:3.11-slim`):** Cài các gói hệ thống cần để biên dịch (`gcc`, `libpq-dev`), sau đó cài thư viện Python bằng `pip install --no-cache-dir --user -r requirements.txt` vào `/root/.local`.
- **Stage 2 (`runtime`, từ `python:3.11-slim`):** Tạo non-root user `appuser`, chỉ `COPY --from=builder /root/.local /home/appuser/.local` (các package đã cài sẵn) cùng mã nguồn `main.py` và `utils/mock_llm.py`, cấu hình `HEALTHCHECK`, chuyển sang `USER appuser` và chạy `uvicorn` trực tiếp.
- **Tại sao image nhỏ hơn?**
  1. Dùng base image `python:3.11-slim` thay vì `python:3.11` đầy đủ.
  2. Toàn bộ build tools (`gcc`, `libpq-dev`, headers, cache build) chỉ nằm ở Stage 1 và bị bỏ lại, không đưa vào image runtime cuối cùng.

#### Kết quả đo thực tế bằng `docker images my-agent`

```text
my-agent:develop   | 1.15GB  (1,154,311,927 bytes ≈ 1154.3 MB)
my-agent:advanced  | 163MB   (162,882,434 bytes   ≈ 162.9 MB)
```

- **Develop (`my-agent:develop`):** `1,154.3 MB` (`1.15 GB`)
- **Production (`my-agent:advanced`):** `162.9 MB` (`163 MB`)
- **Chênh lệch:** Giảm **85.9%** (nhỏ hơn khoảng **7.1 lần**, đạt chuẩn `< 500 MB`).

### Exercise 2.4: Docker Compose stack (`02-docker/production/`)

#### Kiến trúc các service và cách giao tiếp

```text
                     Port 80 / 443 (Host)
                              │
                              ▼
                   ┌─────────────────────┐
                   │   nginx (alpine)    │  Reverse proxy, rate limit (10r/s),
                   │   ports: 80, 443    │  security headers, upstream balance
                   └──────────┬──────────┘
                              │  (Docker bridge network: internal)
                              ▼
                   ┌─────────────────────┐
                   │   agent (FastAPI)   │  Port 8000 (chỉ nội bộ, không expose ra host)
                   │   uvicorn 2 workers │  depends_on: redis & qdrant (service_healthy)
                   └────┬───────────┬────┘
                        │           │
         redis://redis:6379/0    http://qdrant:6333
                        │           │
                        ▼           ▼
             ┌────────────────┐  ┌─────────────────────┐
             │ redis:7-alpine │  │ qdrant/qdrant:v1.9.0│
             │ volume:        │  │ volume:             │
             │ redis_data     │  │ qdrant_data         │
             └────────────────┘  └─────────────────────┘
```

- **4 service được khởi động:** `nginx`, `agent`, `redis`, `qdrant`.
- **Cách giao tiếp:** Tất cả cùng tham gia mạng bridge nội bộ `internal`, giao tiếp bằng Docker DNS theo tên service (`http://agent:8000`, `redis://redis:6379/0`, `http://qdrant:6333`). Chỉ duy nhất `nginx` mở cổng `80`/`443` ra host; `agent`, `redis`, `qdrant` được cô lập bên trong.

#### Kết quả chạy và kiểm thử qua Nginx

Lệnh chạy: `docker compose -p k5-day14-docker up -d --build` (đã tạo `.env.local` trước đó).

Trạng thái `docker compose -p k5-day14-docker ps`:

```text
NAME                       IMAGE                   SERVICE   STATUS                    PORTS
k5-day14-docker-agent-1    k5-day14-docker-agent   agent     Up 21 seconds (healthy)   8000/tcp
k5-day14-docker-nginx-1    nginx:alpine            nginx     Up 18 seconds             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
k5-day14-docker-qdrant-1   qdrant/qdrant:v1.9.0    qdrant    Up 34 seconds (healthy)   6333-6334/tcp
k5-day14-docker-redis-1    redis:7-alpine          redis     Up 33 seconds (healthy)   6379/tcp
```

Kết quả test qua Nginx:

- `curl http://localhost/health`:
  ```json
  {"status":"ok","uptime_seconds":14.8,"version":"2.0.0","timestamp":"2026-11-25T08:02:04.529797"}
  ```
- `curl -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'`:
  ```json
  {"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
  ```

Sau khi test xong đã dọn sạch stack và volumes bằng `docker compose -p k5-day14-docker down -v`.

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Deploy agent Part 6 lên Render

- **Public URL:** `https://k5-l3a-day14-nguyenthanhdanh-2a202603493.onrender.com`
- **Cấu hình:** Deploy từ thư mục `06-lab-complete/` trên **Render** bằng `Dockerfile` (multi-stage) và `render.yaml`, kết nối Redis cloud qua biến môi trường `REDIS_URL`, bảo vệ bằng `AGENT_API_KEY` đặt trong Render Environment (không commit secret vào repo).
- **Kết quả kiểm tra thực tế:**
  - `GET /health` → `200` (`{"status":"ok",...}`)
  - `GET /ready` → `200` (`{"ready":true,"redis":"connected"}`)
  - `POST /ask` (không có key) → `401` (`{"detail":"Invalid or missing API key"}`)
  - `POST /ask` (có `X-API-Key`) → `200`
- **Chi tiết & lệnh kiểm tra:** xem [DEPLOYMENT.md](DEPLOYMENT.md) và ảnh trong `screenshots/` (`dashboard.png`, `running.png`, `test.png`).

### Exercise 3.2: So sánh `railway.toml` vs `render.yaml`

| Tiêu chí | `railway.toml` (Railway) | `render.yaml` (Render Blueprint) |
| :--- | :--- | :--- |
| **Định dạng & phạm vi** | TOML; cấu hình cho **một service** (build + deploy), các service phụ như Redis hay biến môi trường thường quản lý trực tiếp trên dashboard/CLI. | YAML (Infrastructure as Code); khai báo được **nhiều service cùng lúc** (web service, Redis/DB, worker) trong cùng một file Blueprint. |
| **Cách khai báo build** | `[build]` với `builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`. | Trong từng phần tử của `services:`: `type: web`, `runtime: docker`, `plan: free`. |
| **Health check** | `[deploy]` dùng `healthcheckPath = "/health"` và `healthcheckTimeout = 30`. | Dùng `healthCheckPath: /health` ngay dưới định nghĩa service. |
| **Quản lý biến môi trường & secret** | Không khai báo secret trong `railway.toml`; đặt qua Railway Variables hoặc CLI (`railway variables set`). | Khai báo danh sách `envVars:` trực tiếp trong YAML; secret dùng `generateValue: true` (Render tự sinh) hoặc `sync: false` (nhập tay trên dashboard, không ghi giá trị thật vào Git). |
| **Chính sách restart** | Khai báo rõ `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3`. | Render tự quản lý restart mặc định khi container crash hoặc fail health check. |

### Exercise 3.3: GCP Cloud Run CI/CD Pipeline (`03-cloud-deployment/production-cloud-run/`)

Đọc `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD trên Google Cloud đi qua 4 bước tuần tự khi có commit/trigger:
1. **Test (`python:3.11-slim`):** Cài dependencies từ `requirements.txt` cùng `pytest` và chạy toàn bộ test trong `tests/`; chỉ khi test pass mới đi tiếp.
2. **Build (`gcr.io/cloud-builders/docker`):** Build Docker image gắn 2 tag `$COMMIT_SHA` và `latest`, tận dụng `--cache-from=...:latest` để tăng tốc build.
3. **Push:** Đẩy các image tag lên Google Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **Deploy (`gcloud run deploy` + `service.yaml`):** Triển khai bản `$COMMIT_SHA` lên Cloud Run (`asia-southeast1`), cấu hình autoscaling (`minScale=1` tránh cold start, `maxScale=10`, `containerConcurrency=80`), giới hạn tài nguyên (`1 CPU`, `512Mi RAM`), gắn `livenessProbe` (`/health`) + `startupProbe` (`/ready`), và inject secret (`OPENAI_API_KEY`, `AGENT_API_KEY`) an toàn từ **Secret Manager** thay vì hardcode.

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/app.py`)

- **API key được check ở đâu?** Trong dependency `verify_api_key(api_key: str = Security(api_key_header))` (dòng 39–54), đọc header `X-API-Key` qua `APIKeyHeader(name="X-API-Key", auto_error=False)` và inject vào endpoint `POST /ask` bằng `Depends(verify_api_key)`. Endpoint `/` và `/health` được để public để nền tảng gọi health check.
- **Điều gì xảy ra nếu thiếu hoặc sai key?**
  - Thiếu header `X-API-Key` → trả về **`401 Unauthorized`** (`Missing API key. Include header: X-API-Key: <your-key>`).
  - Có header nhưng sai giá trị → trả về **`403 Forbidden`** (`Invalid API key.`).
- **Làm sao rotate key không bị downtime?**
  - Lưu key trong biến môi trường (`AGENT_API_KEY`) hoặc secrets manager (không hardcode).
  - Khi rotate trong production: hỗ trợ tạm thời **2 key song song** (key cũ + key mới, ví dụ `AGENT_API_KEYS=old_key,new_key`), cập nhật các client sang key mới, sau khi kiểm tra không còn traffic dùng key cũ mới xoá key cũ khỏi biến môi trường và reload/redeploy.

**Kết quả test thực tế (`AGENT_API_KEY=secret-key-123`):**

```text
# 1. Không có key → 401
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# 2. Sai key (X-API-Key: wrong-key) → 403
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

# 3. Đúng key (X-API-Key: secret-key-123) → 200
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

- **JWT flow (`auth.py`):**
  1. Client gửi `POST /auth/token` với `username` / `password` (`student` / `demo123` cho role `user`, hoặc `teacher` / `teach456` cho role `admin`).
  2. Server xác thực qua `authenticate_user()`, tạo JWT ký bằng `HS256` chứa payload `sub`, `role`, `iat`, `exp` (hết hạn sau 60 phút).
  3. Khi gọi `POST /ask`, client gửi `Authorization: Bearer <TOKEN>`. Dependency `verify_token()` giải mã và kiểm tra chữ ký + hạn dùng stateless (không cần truy vấn DB mỗi request).
- **Rate limiter (`rate_limiter.py`):**
  - **Thuật toán:** **Sliding Window** (dùng `deque` lưu timestamp các request của từng `user_id` trong cửa sổ trượt 60 giây, xoá các timestamp cũ hơn `now - 60`).
  - **Giới hạn:** `rate_limiter_user` là **10 requests/phút** (`window_seconds=60`); `rate_limiter_admin` là **100 requests/phút**.
  - **Bypass / nâng giới hạn cho admin:** Trong `app.py` (dòng 141), kiểm tra `role = user["role"]` từ JWT payload rồi chọn limiter tương ứng (`rate_limiter_admin if role == "admin" else rate_limiter_user`), hoặc bỏ qua bước gọi `limiter.check()` nếu `role == "admin"`.
  - **Tại sao cần cả Rate Limit và Cost Guard?** Rate limit giới hạn **tốc độ gọi** (chống spam/DDoS, bảo vệ CPU/băng thông trong ngắn hạn), còn Cost guard giới hạn **tổng chi phí tiền** theo token/ngân sách ngày hoặc tháng (vì một vài request hợp lệ dưới rate limit nhưng prompt/output rất dài vẫn có thể đốt hết ngân sách LLM).

**Kết quả test thực tế (lấy token `student`/`demo123` và gọi lặp 12 lần):**

```text
# Lấy token tại POST /auth/token → 200 OK
access_token: eyJhbGciOiJIUzI1Ni... (đã che token)

# Vòng lặp 12 request tới POST /ask với Authorization: Bearer <REDACTED>
Req 1:  HTTP 200  (requests_remaining: 9)
Req 2:  HTTP 200  (requests_remaining: 8)
Req 3:  HTTP 200  (requests_remaining: 7)
Req 4:  HTTP 200  (requests_remaining: 6)
Req 5:  HTTP 200  (requests_remaining: 5)
Req 6:  HTTP 200  (requests_remaining: 4)
Req 7:  HTTP 200  (requests_remaining: 3)
Req 8:  HTTP 200  (requests_remaining: 2)
Req 9:  HTTP 200  (requests_remaining: 1)
Req 10: HTTP 200  (requests_remaining: 0)
Req 11: HTTP 429  {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
Req 12: HTTP 429  {"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost Guard (`cost_guard.py`)

- **Cơ chế hoạt động trong bản mẫu & cách triển khai production với Redis:**
  - Trước khi gọi LLM, gọi `check_budget(user_id)`: so sánh chi phí tích luỹ với ngân sách (per-user `$1/ngày` trong demo hoặc `$10/tháng` theo đề bài, kèm global budget). Nếu vượt ngân sách → chặn ngay và trả **`402 Payment Required`** (hoặc `503` khi hết global budget); nếu đạt ≥ 80% → ghi log cảnh báo.
  - Sau khi LLM trả lời, tính chi phí theo số `input_tokens` và `output_tokens` rồi gọi `record_usage()` để cộng dồn.
  - **Trong production (stateless, nhiều instance):** Không lưu `_records` trong RAM mà lưu trong **Redis** với key theo kỳ, ví dụ `budget:{user_id}:{YYYY-MM}` (hoặc `{YYYY-MM-DD}`), cập nhật bằng lệnh atomic `INCRBYFLOAT` và đặt `EXPIRE` (TTL 32 ngày cho budget tháng / 2 ngày cho budget ngày) để tự reset sang kỳ mới.
- **Kết quả kiểm tra `GET /me/usage` sau 10 request:**
  ```json
  {"user_id":"student","date":"2026-11-25","requests":10,"input_tokens":40,"output_tokens":320,"cost_usd":0.000198,"budget_usd":1.0,"budget_remaining_usd":0.999802,"budget_used_pct":0.0}
  ```

---

## Part 5: Scaling & Reliability

### Exercise 5.1 & 5.2: Health Checks (`/health` vs `/ready`) và Graceful Shutdown (`05-scaling-reliability/develop/app.py`)

- **Phân biệt Liveness (`/health`) và Readiness (`/ready`):**
  - **`GET /health` (Liveness probe):** Trả lời câu hỏi *"Process còn sống không?"*. Luôn trả `200` khi process hoạt động bình thường (kể cả khi dependency tạm mất, chỉ báo `status: "degraded"` nếu cần). Nếu `/health` fail hoặc timeout, orchestrator sẽ **restart container**.
  - **`GET /ready` (Readiness probe):** Trả lời câu hỏi *"Instance đã sẵn sàng nhận traffic chưa?"*. Trả `503 Service Unavailable` khi app đang khởi động, đang shutdown (`_is_ready = False`), hoặc mất kết nối dependency thiết yếu (Redis/DB). Khi `/ready` trả 503, load balancer **ngừng route traffic mới** vào instance đó mà không cần restart container.
- **Kết quả test thực tế bản `develop`:**
  - `GET /health` → `200 OK`:
    ```json
    {"status":"degraded","uptime_seconds":1.5,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:20:43.275259+00:00","checks":{"memory":{"status":"degraded","used_percent":90.1}}}
    ```
  - `GET /ready` → `200 OK`:
    ```json
    {"ready":true,"in_flight_requests":1}
    ```
- **Graceful Shutdown:**
  - Middleware `track_requests` đếm số request đang xử lý (`_in_flight_requests`).
  - Khi nhận tín hiệu `SIGTERM` (từ `docker stop` hoặc rolling deploy), uvicorn kích hoạt nhánh shutdown của `lifespan`: đặt `_is_ready = False` (để load balancer ngừng gửi request mới), chờ tối đa 30s (`timeout_graceful_shutdown=30`) cho tất cả request đang chạy hoàn tất rồi mới đóng kết nối và thoát với exit code `0`.

### Exercise 5.3, 5.4 & 5.5: Stateless Design, Horizontal Scaling (`--scale agent=3`) và Test thực tế

- **Vì sao state trong RAM bị hỏng khi scale nhiều instance?**
  - Khi chạy 3 instance sau Nginx load balancer, request 1 của user có thể vào `instance-A` (lưu lịch sử hội thoại trong RAM của `instance-A`), nhưng request 2 lại được điều phối sang `instance-B` → `instance-B` không thấy lịch sử cũ, làm mất ngữ cảnh hoặc lỗi phiên làm việc.
- **Giải pháp Stateless (`05-scaling-reliability/production/app.py`):**
  - Chuyển toàn bộ session & conversation history sang **Redis** (`session:{session_id}` với TTL 3600s, giữ tối đa 20 messages). Mọi instance đều đọc/ghi cùng một nguồn chân lý nên có thể scale ngang hoặc restart bất kỳ instance nào mà không mất dữ liệu.

**Kết quả chạy stack 3 instance (`docker compose -p k5-day14-scaling up -d --build --scale agent=3`):**

```text
NAME                       IMAGE                    SERVICE   STATUS                    PORTS
k5-day14-scaling-agent-1   k5-day14-scaling-agent   agent     Up 12 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-2   k5-day14-scaling-agent   agent     Up 13 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-3   k5-day14-scaling-agent   agent     Up 12 seconds (healthy)   8000/tcp
k5-day14-scaling-nginx-1   nginx:alpine             nginx     Up 11 seconds             0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   redis:7-alpine           redis     Up 23 seconds (healthy)   6379/tcp
```

**Kết quả chạy `python test_stateless.py` (5 request liên tiếp qua `http://localhost:8080/chat`):**

```text
Session ID: 90e9997b-5dc8-4e06-a880-20b168f32b26

Request 1: [instance-d89a27]  Q: What is Docker?
Request 2: [instance-4ef22f]  Q: Why do we need containers?
Request 3: [instance-79c8b2]  Q: What is Kubernetes?
Request 4: [instance-d89a27]  Q: How does load balancing work?
Request 5: [instance-4ef22f]  Q: What is Redis used for?

Total requests: 5
Instances used: {'instance-79c8b2', 'instance-d89a27', 'instance-4ef22f'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10 (5 user + 5 assistant)
✅ Session history preserved across all instances via Redis!
```

- **Giải thích kết quả:** 5 request trong cùng một `session_id` được Nginx chia đều (round-robin) sang cả **3 instance khác nhau** (`instance-d89a27`, `instance-4ef22f`, `instance-79c8b2`), nhưng khi gọi `GET /chat/{session_id}/history` vẫn thu đủ toàn bộ **10 tin nhắn** (5 cặp hỏi–đáp) vì mọi instance đều dùng chung Redis. Sau khi kiểm thử xong đã tắt và dọn stack bằng `docker compose -p k5-day14-scaling down -v`.

---

## Part 6: Final Project (`06-lab-complete/`)

Output chạy `python check_production_ready.py` đầy đủ trên môi trường Linux/Docker (`Dockerfile` multi-stage `201 MB`, `SIGTERM` exit code `0`, `docker stop` exit code `0` trong `0.9s`):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
================================================================
```

---

## AI Log

- **Setup & CP1–CP2:** Dùng AI để đọc cấu trúc đề bài, chạy kiểm thử thực tế các ứng dụng Part 1 (`develop`, `production`).
- **CP3–CP4 (Part 4 & Part 5):** Dùng AI để đọc mã nguồn `04-api-gateway/` và `05-scaling-reliability/`, chạy kiểm thử thực tế API Key (`401`/`403`/`200`), JWT (`/auth/token`), vòng lặp Rate Limit (`429`), Cost Guard (`/me/usage`), Health/Readiness probes, và Docker Compose stack `--scale agent=3` kèm `test_stateless.py`.
- **CP5 (Part 6 — `06-lab-complete/`):** Dùng AI để hoàn thiện toàn bộ các module trong `06-lab-complete/app/` (`config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`) cùng `Dockerfile` (multi-stage dùng `public.ecr.aws/docker/library/python:3.11-slim`), `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`, và chạy kiểm tra thực tế bằng `check_production_ready.py` (không sửa script chấm).
- **CP6–CP8 (Part 3 & Part 7):** Dùng AI hỗ trợ viết `DEPLOYMENT.md`; chạy thực tế toàn bộ load test (`reports/load_v2_*.json`), eval v1/v2, bổ sung 2 entry (`security-02`, `scaling-03`) vào `KNOWLEDGE_BASE` trong `mock_llm.py` để đạt 23/23 (`eval_v2_fixed.json`), kích hoạt alert firing trên Prometheus, trích xuất `trace_id` + log JSON thực tế từ Jaeger/container.
