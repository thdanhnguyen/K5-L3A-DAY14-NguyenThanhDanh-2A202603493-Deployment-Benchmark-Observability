# Benchmark & Observability Report — Day 14

**Họ tên:** Nguyễn Thành Danh
**MSSV:** 2A202603493
**Môi trường:** Windows + Python 3.12.4 (`.venv`), Docker Desktop 29.8.1 (Compose v5.5.1)

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | ≤ 500 ms | 95% người dùng nhận câu trả lời dưới nửa giây, đảm bảo trải nghiệm mượt mà đồng thời chấp nhận một tỉ lệ nhỏ tail latency (3% request chậm). |
| Error rate `/ask` | ≤ 2.0 % | Cao hơn tỉ lệ lỗi upstream mô phỏng mặc định (`MOCK_ERROR_RATE=1%`) một khoảng đệm nhỏ, giúp cảnh báo sớm khi upstream hoặc hệ thống suy giảm thực sự. |
| Accuracy trên golden dataset | ≥ 80 % (và 100% sau khi bổ sung KB, 0 regression) | Đảm bảo chất lượng câu trả lời ổn định trước mỗi lần deploy; quality gate chặn mọi bản sửa làm giảm độ chính xác so với baseline. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

Số liệu lấy trực tiếp từ `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json` (mỗi mức 300 request):

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.14 | 197.3 | 240.2 | 1698.3 | 0.00% | ✅ PASS |
| 10 | 36.70 | 194.4 | 234.6 | 1693.5 | 0.67% | ✅ PASS |
| 50 | 139.01 | 194.2 | 252.8 | 299.8 | 1.00% | ✅ PASS |
| 100 | 63.97 | 369.9 | 3131.3 | 3265.0 | 0.67% | ❌ FAIL |

**Nhận xét:** RPS không tăng tuyến tính theo concurrency. Từ `c=1` → `10` → `50`, RPS tăng mạnh (`4.14 → 36.70 → 139.01 req/s`) trong khi p50 giữ ổn định ~195 ms vì event loop async xử lý tốt I/O chờ LLM. Tuy nhiên đến `c=100`, hệ thống chạm ngưỡng bão hoà (event loop/socket backlog trên 1 worker đơn lẻ bị nghẽn), làm RPS tụt xuống còn `63.97 req/s` và p95 vọt lên `3131.3 ms` (vi phạm SLO ≤ 500 ms).

### 2.2 Tail latency

Số liệu lấy trực tiếp từ `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json` (300 request, `concurrency=20`):

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 187.2 | 226.2 | 235.9 |
| 0.03 | 216.4 | 234.1 | 1702.2 |
| 0.1 | 351.3 | 1682.5 | 1713.2 |

**Nhận xét:** **p99 và p95 nhạy nhất** với các request chậm bất thường (tail latency). Ở `MOCK_SLOW_RATE=0.03`, `avg` chỉ tăng nhẹ từ `187.2 ms → 216.4 ms` (+15.6%) trông có vẻ ổn, nhưng `p99` đã tăng gấp **7.2 lần** (`235.9 ms → 1702.2 ms`). Đến `0.1`, `avg` vẫn chỉ `351.3 ms` (< 500 ms) nhưng `p95` đã vọt lên `1682.5 ms`. Vì vậy SLO **không nên đặt theo average** vì giá trị trung bình che giấu trải nghiệm rất tệ của 1–5% người dùng bị kẹt ở đuôi phân phối.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Số liệu lấy trực tiếp từ `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json` (23 câu trên `golden_dataset.jsonl`):

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 56.3 | 108.7 | 114.5 |
| Tổng cost (USD) | \$0.000393 | \$0.000756 | \$0.000798 |
| Cost / câu đúng (USD) | \$0.00039315 | \$0.00003599 | \$0.00003468 |
| Quality gate | FAIL | PASS (≥ 80%, 0 regression) | PASS (≥ 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry về JWT vs API key (kích hoạt bởi `jwt`, `api key`, `xác thực`) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry về Kubernetes HPA (kích hoạt bởi `hpa`, `kubernetes`, `autoscaling`) vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (và đồng bộ sang `production/utils/mock_llm.py`). |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- Agent v2 tốn gần gấp đôi số token (`56.3 → 114.5 tokens/câu`) và tổng chi phí (`\$0.000393 → \$0.000798`) do chèn thêm ngữ cảnh retrieval vào prompt, đồng thời thêm ~20 ms latency tìm kiếm KB.
- Tuy nhiên độ chính xác tăng vọt từ `4.3% → 100.0%`, nên **cost / câu đúng** lại giảm hơn **11 lần** (`\$0.00039315 → \$0.00003468`). Điều này cho thấy nên so sánh các phiên bản agent bằng **"cost trên mỗi câu trả lời đúng"** thay vì chỉ nhìn tổng chi phí hay cost/câu.

**Cách tích hợp Quality Gate vào CI/CD để chặn merge (Exercise 7.3):**
- Script `eval/run_eval.py` trả về **exit code `0`** khi đạt `--min-accuracy` và không có câu nào bị regression so với `--baseline`, ngược lại trả về **exit code `1`**.
- Trong GitHub Actions (job chạy trên mỗi Pull Request), khởi động agent v2 ở background rồi chạy:
  ```yaml
  - name: Run Eval Quality Gate
    run: |
      python eval/run_eval.py --url http://localhost:8002 \
        --min-accuracy 0.95 \
        --baseline reports/eval_v2.json \
        --out reports/eval_pr.json
  ```
- Khi kết hợp với Branch Protection Rule (bắt buộc status check này pass), mọi PR làm tụt accuracy dưới ngưỡng hoặc gây regression sẽ trả exit code `1` và **tự động chặn merge**.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (`screenshots/grafana-dashboard.png` — mở `http://localhost:3000`)
- [x] Một trace chậm trong Jaeger (`screenshots/jaeger-slow-trace.png` — mở `http://localhost:16686/trace/357b4a66fa143b66e05cf6dd44b02138`)
- [x] Một trace lỗi trong Jaeger (`screenshots/jaeger-error-trace.png` — mở `http://localhost:16686/trace/6d6713f18ceeb684fdfa4c9f8e1861c5`)
- [x] Trang Alerts của Prometheus với 2 alert đang **firing** (`screenshots/prometheus-alert-firing.png` — mở `http://localhost:9090/alerts`)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`severity: critical`, error rate đo được `21.93%` > 5%) | ~75 giây (`for: 1m` + 1 chu kỳ scrape 15s) | Error Rate (%) & HTTP Status 5xx trên Grafana |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`severity: warning`, p95 đo được `1.915s` > 1s) | ~135 giây (`for: 2m` + 1 chu kỳ scrape 15s) | Latency p50/p95/p99 (ms) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (khi lưu lượng đủ để burn rate > \$2/giờ) và `AgentHighLatencyP95` (do `latency_factor=2.5`) | ~135 giây (`for: 2m` + chu kỳ scrape) | LLM Cost Burn Rate (\$/h) & Latency p95 |
| D | `docker pause` 1 instance | `AgentInstanceDown` (`up{job="agent"} == 0`) | ~45 giây (`for: 30s` + chu kỳ scrape 15s) | Active Instances / Target Up |
| E | `AGENT_VERSION=v1` | Không có alert nào firing (vì HTTP vẫn trả `200`, latency còn thấp hơn và cost rẻ hơn!) | N/A | Token/request và Cost giảm nhẹ, nhưng Golden Signals (Traffic/Latency/Errors/Saturation) vẫn "xanh" |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Đây là dạng **silent quality degradation** (hệ thống vẫn trả HTTP 200 nhanh và rẻ, nhưng câu trả lời sai). Để phát hiện trong production cần kết hợp:
1. **CI/CD Eval Quality Gate:** Chạy `eval/run_eval.py` trên golden dataset trước mỗi lần deploy, chặn merge nếu accuracy tụt hoặc có regression.
2. **Scheduled synthetic eval (Canary eval):** Chạy định kỳ bộ câu hỏi mẫu trên production và xuất metric `agent_eval_accuracy` vào Prometheus để đặt alert khi accuracy giảm.
3. **Online quality signals & LLM-as-a-judge sampling:** Theo dõi phản hồi người dùng (thumbs down, tỉ lệ hỏi lại), giám sát độ dài câu trả lời / tỉ lệ retrieval hit bất thường, và chấm điểm tự động một mẫu nhỏ (1–5%) traffic thật.

### 4.3 Debug bằng trace

Chọn 1 trace chậm thực tế lấy từ stack đang chạy (và đối chiếu trực tiếp với log JSON của container `k5-day14-observability-agent-1`):

- `trace_id`: `357b4a66fa143b66e05cf6dd44b02138`
- Tổng thời gian: `1688.3 ms`
- Span chiếm nhiều thời gian nhất: `llm_call` / `llm.generate` (`1662.6 ms`, chiếm **98.5%** tổng thời gian request; phần còn lại ~25.7 ms là retrieval + overhead FastAPI)
- Dòng log JSON tương ứng (grep theo `trace_id` `357b4a66fa143b66e05cf6dd44b02138`):

```json
{"ts": "2026-11-25T09:52:41.442670+00:00", "level": "INFO", "service": "observable-agent", "instance": "5e9695c325c8", "event": "http_request", "trace_id": "357b4a66fa143b66e05cf6dd44b02138", "span_id": "4a93f1b1e9adc49b", "request_id": "409889a4c5b0", "method": "POST", "route": "/ask", "status": 200, "ms": 1688.3}
```

*(Trace lỗi tham khảo trong Jaeger để chụp `jaeger-error-trace.png`: `trace_id` = `6d6713f18ceeb684fdfa4c9f8e1861c5`, `status: 503`, `ms: 855.7`, lỗi `Upstream LLM error: 503 Service Unavailable (mock)`.)*

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Số liệu lấy trực tiếp từ `benchmark-results/scale_1_stats.csv` và `benchmark-results/scale_3_stats.csv` (dòng `Aggregated` — và ghi chú riêng `POST /ask`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 57.45 (POST `/ask`: 52.33) | 210 | 1900 | 2900 | 59 (0.88%) |
| 3 | 61.84 (POST `/ask`: 56.59) | 200 | 1700 | 2900 | 76 (1.04%) |

**Giải thích kết quả:**
- Khi tăng từ **1 → 3 instance**, **p95 giảm từ `1900 ms → 1700 ms`** (đặc biệt **p90 của `/ask` giảm hơn một nửa từ `1300 ms → 540 ms`** và `avg` giảm từ `425.4 ms → 331.3 ms`), đồng thời RPS tăng từ `57.45 → 61.84 req/s`.
- Tuy nhiên **p99 vẫn giữ ở `2900 ms`** và RPS không tăng gấp 3 vì **nút thắt chính nằm ở độ trễ chờ upstream LLM (I/O-bound)** kèm `MOCK_SLOW_RATE=3%` (+1500 ms tail latency) và `wait_time` giữa các request của 100 Locust user cố định. Scale ngang giúp giảm mạnh hiện tượng xếp hàng CPU/event-loop ở mức tải trung bình–cao (cải thiện `avg`, `p90`, `p95`), nhưng không thể xoá bỏ tail latency vốn sinh ra từ upstream LLM — muốn giảm tiếp p99 cần thêm timeout/retry có hedge, caching hoặc fallback model.

---

## 6. Kết luận

- 3 điều học được về benchmark & observability:
  1. **Không bao giờ đánh giá hiệu năng chỉ bằng latency trung bình:** Tail latency (`p95`/`p99`) mới phản ánh trải nghiệm thực tế của người dùng khi có 3–10% request chậm.
  2. **Chất lượng (eval) phải đi cùng hiệu năng & chi phí:** Một bản deploy có thể nhanh hơn, rẻ hơn và HTTP 200 100% nhưng trả lời sai hoàn toàn (như thí nghiệm E `v1`); dùng **cost / câu đúng** và **CI eval quality gate** giúp bắt regression trước khi lên production.
  3. **Ba trụ cột Observability (Metrics + Traces + Structured Logs) bổ trợ lẫn nhau:** Prometheus/Grafana báo *cái gì* đang xấu (alert firing), Jaeger chỉ *chỗ nào* chậm/lỗi theo từng span, và log JSON gắn `trace_id` giúp truy ra chi tiết request ngay lập tức.
- Nếu đưa agent này lên production thật, nên thêm các metric / alert sau:
  - **TTFT (Time To First Token)** và **tokens/giây** cho streaming response.
  - **Retrieval hit rate / empty context rate** và **scheduled eval accuracy** để phát hiện sớm suy giảm chất lượng RAG/LLM.
  - **Rate-limit rejection rate (`429`)** và **budget exhaustion (`402`)** theo tenant/API key để phát hiện sớm hành vi lạm dụng hoặc khách hàng chạm hạn mức.
  - **Redis connection pool saturation & latency** vì Redis nằm trên critical path của auth/rate-limit/cost-guard.
